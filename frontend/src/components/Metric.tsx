export function Metric(props: { label: string; value: number; tone: string }) {
  return (
    <div className="metric" data-tone={props.tone}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}
