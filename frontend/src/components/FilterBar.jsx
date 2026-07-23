export default function FilterBar({ selected, onChange }) {
    const filters = [
        { value: null, label: "All Sources", emoji: "🔍" },
        { value: "10-K", label: "Annual (10-K)", emoji: "📊" },
        { value: "10-Q", label: "Quarterly (10-Q)", emoji: "📋" },
        { value: "news", label: "News", emoji: "📰" },
    ];

    return (
        <div className="flex gap-2 mb-4 flex-wrap">
            {filters.map(f => (
                <button
                    key={String(f.value)}
                    onClick={() => onChange(f.value)}
                    className={`px-4 py-2 rounded-full text-sm border transition-colors
                        ${selected === f.value
                            ? "bg-blue-600 text-white border-blue-600"
                            : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                        }`}
                >
                    {f.emoji} {f.label}
                </button>
            ))}
        </div>
    );
}