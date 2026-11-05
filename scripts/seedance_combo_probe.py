from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.evolink_client import evolink_base, evolink_platform_api_key  # noqa: E402


def _build_prompt(identity_count: int, *, include_opening: bool, include_video: bool) -> str:
    parts: list[str] = []
    if include_opening:
        parts.append(
            "@Image1 is the opening frame at t=0. Keep its scene, framing, lighting and wardrobe."
        )
    if identity_count > 0:
        first_idx = 2 if include_opening else 1
        tags = ", ".join(f"@Image{i}" for i in range(first_idx, first_idx + identity_count))
        parts.append(
            f"{tags} are the same person from identity reference angles. Use them for face, "
            "hair, body proportions and outfit continuity only."
        )
    if include_video:
        parts.append(
            "@Video1 provides camera movement, timing and motion only. Ignore the reference actor's face and identity."
        )
    parts.append(
        "A woman stands in the same room, looks toward camera, makes one small hand gesture, "
        "then shifts weight naturally. Same face and same outfit throughout. No text or watermark."
    )
    return "\n\n".join(parts)


def _build_body(
    *,
    opening_frame_url: str | None,
    identity_urls: list[str],
    motion_video_url: str | None,
    duration: int,
    quality: str,
    aspect_ratio: str,
    include_opening: bool,
    include_identity: bool,
    include_video: bool,
    generate_audio: bool,
) -> dict[str, Any]:
    image_urls: list[str] = []
    if include_opening and opening_frame_url:
        image_urls.append(opening_frame_url)
    if include_identity:
        image_urls.extend(identity_urls)
    body: dict[str, Any] = {
        "model": "seedance-2.0-fast-reference-to-video" if include_video else "seedance-2.0-text-to-video",
        "prompt": _build_prompt(
            len(identity_urls) if include_identity else 0,
            include_opening=include_opening and bool(opening_frame_url),
            include_video=include_video and bool(motion_video_url),
        ),
        "duration": int(duration),
        "quality": quality,
        "aspect_ratio": "adaptive" if include_video else aspect_ratio,
        "generate_audio": bool(generate_audio),
        "content_filter": True,
    }
    if image_urls:
        body["image_urls"] = image_urls[:30]
    if include_video and motion_video_url:
        body["video_urls"] = [motion_video_url]
    return body


async def _submit(client: httpx.AsyncClient, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    url = f"{evolink_base()}/v1/videos/generations"
    resp = await client.post(url, headers=headers, json=body)
    data: dict[str, Any]
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text}
    return {
        "status_code": resp.status_code,
        "response": data,
        "request": body,
    }


async def main_async(args: argparse.Namespace) -> int:
    api_key = args.api_key or os.getenv("EVOLINK_PLATFORM_API_KEY") or evolink_platform_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    cases: list[tuple[str, dict[str, Any]]] = [
        (
            "all_inputs",
            _build_body(
                opening_frame_url=args.opening_frame_url,
                identity_urls=args.identity_url,
                motion_video_url=args.motion_video_url,
                duration=args.duration,
                quality=args.quality,
                aspect_ratio=args.aspect_ratio,
                include_opening=True,
                include_identity=True,
                include_video=True,
                generate_audio=args.generate_audio,
            ),
        )
    ]
    if args.ablate:
        cases.extend(
            [
                (
                    "no_opening_frame",
                    _build_body(
                        opening_frame_url=args.opening_frame_url,
                        identity_urls=args.identity_url,
                        motion_video_url=args.motion_video_url,
                        duration=args.duration,
                        quality=args.quality,
                        aspect_ratio=args.aspect_ratio,
                        include_opening=False,
                        include_identity=True,
                        include_video=True,
                        generate_audio=args.generate_audio,
                    ),
                ),
                (
                    "no_identity_refs",
                    _build_body(
                        opening_frame_url=args.opening_frame_url,
                        identity_urls=args.identity_url,
                        motion_video_url=args.motion_video_url,
                        duration=args.duration,
                        quality=args.quality,
                        aspect_ratio=args.aspect_ratio,
                        include_opening=True,
                        include_identity=False,
                        include_video=True,
                        generate_audio=args.generate_audio,
                    ),
                ),
                (
                    "no_motion_video",
                    _build_body(
                        opening_frame_url=args.opening_frame_url,
                        identity_urls=args.identity_url,
                        motion_video_url=args.motion_video_url,
                        duration=args.duration,
                        quality=args.quality,
                        aspect_ratio=args.aspect_ratio,
                        include_opening=True,
                        include_identity=True,
                        include_video=False,
                        generate_audio=args.generate_audio,
                    ),
                ),
            ]
        )

    results: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=120.0) as client:
        for name, body in cases:
            results[name] = await _submit(client, headers, body)

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved report: {out_path}")
    for name, payload in results.items():
        status_code = payload.get("status_code")
        response = payload.get("response") or {}
        task_id = response.get("id") if isinstance(response, dict) else None
        status = response.get("status") if isinstance(response, dict) else None
        print(f"{name}: http={status_code} task_id={task_id or '-'} status={status or '-'}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Probe whether our Seedance/EvoLink provider accepts opening frame + identity refs + motion video together."
    )
    p.add_argument("--opening-frame-url", required=True, help="Public HTTPS URL for opening frame image.")
    p.add_argument(
        "--identity-url",
        action="append",
        default=[],
        help="Public HTTPS URL for one identity reference image. Repeat the flag for multiple refs.",
    )
    p.add_argument("--motion-video-url", required=True, help="Public HTTPS URL for motion reference video.")
    p.add_argument("--api-key", default="", help="Override EVOLINK_PLATFORM_API_KEY.")
    p.add_argument("--duration", type=int, default=5)
    p.add_argument("--quality", default="720p")
    p.add_argument("--aspect-ratio", default="9:16")
    p.add_argument("--generate-audio", action="store_true", default=False)
    p.add_argument("--ablate", action="store_true", help="Also submit 3 comparison cases.")
    p.add_argument(
        "--output",
        default=str(ROOT / "tmp-seedance-combo-probe.json"),
        help="Where to save the JSON report.",
    )
    return p


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if not args.identity_url:
        parser.error("at least one --identity-url is required")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
