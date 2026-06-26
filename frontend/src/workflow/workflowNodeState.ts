export function isWorkflowNodeDisabled(data: Record<string, unknown> | undefined | null): boolean {
  return data?.disabled === true
}
