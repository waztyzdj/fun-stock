export function StatusBadge(props: { status: string }) {
  return (
    <span className="status-badge" data-status={props.status}>
      {props.status}
    </span>
  );
}
