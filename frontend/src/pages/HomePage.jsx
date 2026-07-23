export default function HomePage({ onSelectCompany }) {
    return (
        <div className="max-w-3xl mx-auto px-4 py-16">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
                Stock Research Assistant
            </h1>
            <p className="text-gray-500 mb-8">
                AI-powered Q&A over SEC filings, earnings calls, and news
            </p>
            <button
                onClick={() => onSelectCompany("AAPL")}
                className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
            >
                Test with AAPL →
            </button>
        </div>
    );
}