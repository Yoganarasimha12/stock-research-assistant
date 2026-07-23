export default function StatusBadge({ status }) {
    const styles = {
        pending:  "bg-gray-100 text-gray-600",
        running:  "bg-yellow-100 text-yellow-700",
        done:     "bg-green-100 text-green-700",
        failed:   "bg-red-100 text-red-700",
    };
    const icons = {
        pending: "○",
        running: "◌",
        done:    "✓",
        failed:  "✗",
    };
    return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status] || styles.pending}`}>
            {icons[status]} {status}
        </span>
    );
}