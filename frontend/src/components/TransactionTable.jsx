export default function TransactionTable({ entries, formatDate, formatINR }) {
  return (
    <>
      <h2 className="text-sm font-medium text-white/60 uppercase tracking-widest mt-8 mb-4">
        Ledger
      </h2>
      <div className="bg-white/3 border border-white/8 rounded-xl overflow-hidden">
        {entries.slice(0, 8).map((entry) => (
          <div
            key={entry.id}
            className="flex justify-between items-center px-5 py-3 border-b border-white/5 last:border-0"
          >
            <div>
              <div className="text-xs text-white/70">{entry.description}</div>
              <div className="text-xs text-white/30 mt-0.5">{formatDate(entry.created_at)}</div>
            </div>
            <div
              className={`font-mono text-sm font-medium ${
                entry.amount_paise > 0 ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {entry.amount_paise > 0 ? "+" : ""}
              {formatINR(entry.amount_paise)}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
