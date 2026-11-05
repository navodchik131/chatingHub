"""Аудит маржи: генерации, пакеты кредитов, подписки Standard."""

from __future__ import annotations

import math

from app.config import settings
from app.services.billing_credits import (
    apply_purchase_bonus_credits,
    credits_total_rub,
    legacy_pack_total_rub,
    standard_subscription_monthly_credits,
)
from app.services.plan_catalog import PLAN_SPECS, managed_period_credits
from app.services.studio_evolink_motion_pricing import evolink_video_credit_cost
from app.services.studio_image_pricing import quote_studio_image_credits
from app.services.studio_motion_pricing import (
    grok_imagine_i2v_credit_cost,
    motion_video_credit_cost,
    video_upscale_credit_cost,
)
from app.services.studio_operation_pricing import (
    studio_carousel_shot_credit_cost,
    studio_inpaint_credit_cost,
    studio_model_profile_generate_credit_cost,
    studio_prompt_refine_credit_cost,
    studio_upscale_credit_cost,
)
from app.services.studio_provider_pricing import grok_pipeline_usd, image_model_usd, operation_usd
from app.services.studio_seedance_director_pricing import (
    seedance_director_compose_credit_cost,
    seedance_director_piece_credit_cost,
)

# Входные данные пользователя
RUB_USD = 97.87
ACQUIRING = 0.05
TAX = 0.06
NET = (1 - ACQUIRING) * (1 - TAX)
RUB_PER_CR = RUB_USD / 100


def analyze(name: str, credits: int, api_usd: float, extra: str = "") -> dict:
    api_rub = api_usd * RUB_USD
    rev_net = credits * RUB_PER_CR * NET
    margin = rev_net - api_rub
    pct = (margin / api_rub * 100) if api_rub else 0.0
    be_credits = math.ceil(api_usd * 100 / NET)
    flag = "MINUS" if margin < -0.01 else ("OK" if margin > 0.01 else "~0")
    row = {
        "flag": flag,
        "name": name,
        "credits": credits,
        "api_usd": api_usd,
        "api_rub": api_rub,
        "net_rev": rev_net,
        "margin": margin,
        "pct": pct,
        "be_credits": be_credits,
        "extra": extra,
    }
    print(
        f"{flag:5} {name:45} cr={credits:4} api=${api_usd:.3f} "
        f"api_rub={api_rub:6.1f} net_rev={rev_net:6.1f} margin={margin:+6.1f} ({pct:+5.1f}%) need>={be_credits} {extra}"
    )
    return row


def main() -> None:
    print(f"RUB/USD={RUB_USD}, net_mult={NET:.3f} (5% эквайринг + 6% налог)")
    print("=== GENERATIONS (Credits plan, usd_to_credits markup=0) ===\n")

    minus_rows: list[dict] = []

    models = [
        "nano-banana-2",
        "nano-banana-pro",
        "gpt-image-2",
        "gpt-image-2.5-sunburst",
        "wan-2.7",
        "seedream-v5.0-pro",
    ]
    for m in models:
        cr_none = quote_studio_image_credits(wave_model_id=m, grok_pipeline="none")
        minus_rows.append(analyze(f"image {m} no grok", cr_none, image_model_usd(m)))
        cr_std = quote_studio_image_credits(wave_model_id=m, grok_pipeline="standard")
        minus_rows.append(
            analyze(
                f"image {m} + grok std",
                cr_std,
                image_model_usd(m) + grok_pipeline_usd("standard"),
            )
        )

    cr_wan_pro = quote_studio_image_credits(
        wave_model_id="wan-2.7", wan_edit_tier="pro", grok_pipeline="standard"
    )
    minus_rows.append(
        analyze(
            "image wan-2.7-pro + grok",
            cr_wan_pro,
            image_model_usd("wan-2.7-pro") + grok_pipeline_usd("standard"),
        )
    )

    minus_rows.append(analyze("prompt refine (fixed 2cr)", studio_prompt_refine_credit_cost(), operation_usd("prompt_refine")))
    minus_rows.append(analyze("inpaint", studio_inpaint_credit_cost(), operation_usd("inpaint")))
    minus_rows.append(analyze("image upscale", studio_upscale_credit_cost(), operation_usd("upscale")))
    minus_rows.append(analyze("carousel shot USD fallback", studio_carousel_shot_credit_cost(), operation_usd("carousel_shot")))
    minus_rows.append(analyze("model profile gen", studio_model_profile_generate_credit_cost(), operation_usd("model_profile_generate")))

    minus_rows.append(analyze("motion 10s no ref 720p", motion_video_credit_cost(10, has_motion_reference_video=False), 0.24 * 10))
    minus_rows.append(
        analyze(
            "motion 10s ref 5s+5s 720p",
            motion_video_credit_cost(10, has_motion_reference_video=True, reference_video_duration=5),
            0.13 * 10,
        )
    )
    minus_rows.append(
        analyze(
            "motion 10s ref UNKNOWN dur",
            motion_video_credit_cost(10, has_motion_reference_video=True),
            0.13 * 10,
            "риск если WS считает ref+output",
        )
    )
    minus_rows.append(
        analyze(
            "director piece 10s 720p",
            seedance_director_piece_credit_cost(
                version="2.0", duration_seconds=10, resolution="720p", video_backend="wavespeed"
            ),
            0.20 * 10,
        )
    )
    minus_rows.append(
        analyze(
            "director compose 3 img",
            seedance_director_compose_credit_cost(image_count=3),
            operation_usd("seedance_director_compose") + grok_pipeline_usd("light") * 2,
        )
    )
    minus_rows.append(analyze("grok imagine i2v 6s 720p", grok_imagine_i2v_credit_cost(6, resolution="720p"), 0.14 * 6 + 0.01))
    minus_rows.append(analyze("video upscale 1080p 5s", video_upscale_credit_cost("1080p", duration_seconds=5), 0.15))
    minus_rows.append(
        analyze(
            "evolink 10s output 720p",
            evolink_video_credit_cost(10, has_motion_reference_video=False, variant="standard", resolution="720p"),
            0.149 * 10,
        )
    )
    minus_rows.append(
        analyze(
            "evolink 10s ref 5+5",
            evolink_video_credit_cost(
                10, has_motion_reference_video=True, reference_video_duration=5, variant="standard", resolution="720p"
            ),
            0.091 * 10,
        )
    )

    print("\n=== SUBSCRIPTIONS Standard (только бонусные кредиты vs выручка) ===")
    for spec in sorted(PLAN_SPECS.values(), key=lambda s: (s.tier, s.period)):
        if spec.billing_plan != "standard":
            continue
        period_cr = managed_period_credits(spec)
        if period_cr <= 0:
            continue
        price = spec.price_rub
        net = price * NET
        api_if_spent = period_cr * RUB_PER_CR
        margin = net - api_if_spent
        flag = "MINUS" if margin < -100 else "OK"
        print(
            f"{flag:5} {spec.tier:6} {spec.period:5} price={price:6} bonus_cr={period_cr:5} "
            f"net={net:7.0f} api_value={api_if_spent:7.0f} margin={margin:+8.0f}"
        )

    print("\n=== CREDIT PACKS (без учёта бонусных кредитов) ===")
    for n in [500, 1110, 2500, 5000]:
        rub = float(credits_total_rub(n))
        net = rub * NET
        api = n * RUB_PER_CR
        print(f"pack {n:5} pay={rub:7.0f} net={net:7.0f} api_value={api:7.0f} margin={net - api:+8.0f}")
        if n == 5000:
            bonus_cr = apply_purchase_bonus_credits(n, 5000)
            api_b = bonus_cr * RUB_PER_CR
            print(
                f"  +15% bonus total cr={bonus_cr} api_value={api_b:.0f} margin={net - api_b:+.0f} (те же {rub:.0f} ₽)"
            )

    legacy_cr = int(settings.billing_credit_pack_credits)
    legacy_rub = float(legacy_pack_total_rub())
    print(
        f"legacy {legacy_cr}cr @ {legacy_rub:.0f}₽ net={legacy_rub * NET:.0f} "
        f"api={legacy_cr * RUB_PER_CR:.0f} margin={legacy_rub * NET - legacy_cr * RUB_PER_CR:+.0f}"
    )

    demo_cr = quote_studio_image_credits(wave_model_id="nano-banana-2", grok_pipeline="light")
    print(f"\nreferral signup: {settings.referral_signup_bonus_credits} cr = ${settings.referral_signup_bonus_credits / 100:.2f} чистый минус")
    print(f"demo: {settings.demo_generations_grant} × ~{demo_cr} cr")

    print("\n=== SUMMARY: generations in MINUS (per unit at 97.87₽/$) ===")
    for r in minus_rows:
        if r["flag"] == "MINUS":
            print(f"  - {r['name']}: {r['margin']:+.1f} ₽/gen ({r['pct']:+.1f}%)")


if __name__ == "__main__":
    main()
