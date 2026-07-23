export default function CompanyPage({ ticker, onBack }) {
    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            <button onClick={onBack} className="text-blue-600 mb-4 block">
                ← Back
            </button>
            <h1 className="text-2xl font-bold">{ticker} — Coming Day 16</h1>
        </div>
    );
}