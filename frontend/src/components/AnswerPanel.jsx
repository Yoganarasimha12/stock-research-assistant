import SourceCard from "./SourceCard";

export default function AnswerPanel({ answer, sources, isStreaming }) {
    // Make [Source N] clickable — scroll to that source card
    const renderAnswer = (text) => {
        const parts = text.split(/(\[Source \d+\])/g);
        return parts.map((part, i) => {
            const match = part.match(/\[Source (\d+)\]/);
            if (match) {
                const rank = parseInt(match[1]);
                return (
                    <span
                        key={i}
                        className="text-blue-600 cursor-pointer hover:underline font-medium"
                        onClick={() => {
                            document.getElementById(`source-${rank}`)
                                ?.scrollIntoView({ behavior: "smooth" });
                        }}
                    >
                        {part}
                    </span>
                );
            }
            return <span key={i}>{part}</span>;
        });
    };

    return (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
            {/* Answer header */}
            <div className="flex items-center gap-2 mb-4">
                <h3 className="font-semibold text-gray-800">Answer</h3>
                {isStreaming && (
                    <span className="text-xs text-blue-500 animate-pulse">
                        ● Generating...
                    </span>
                )}
            </div>

            {/* Answer text with clickable citations */}
            <div className="text-gray-800 leading-relaxed whitespace-pre-wrap mb-6">
                {renderAnswer(answer)}
                {isStreaming && (
                    <span className="animate-pulse text-gray-400">▌</span>
                )}
            </div>

            {/* Sources */}
            {sources.length > 0 && (
                <div className="border-t border-gray-100 pt-4">
                    <h4 className="text-sm font-semibold text-gray-600 mb-3">
                        Sources ({sources.length})
                    </h4>
                    <div className="space-y-2">
                        {sources.map(s => (
                            <SourceCard key={s.rank} source={s} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}