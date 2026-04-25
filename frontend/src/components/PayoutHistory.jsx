const statusColors = {
  PENDING: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
  PROCESSING: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  COMPLETED: "bg-green-500/10 text-green-400 border border-green-500/20",
  FAILED: "bg-red-500/10 text-red-400 border border-red-500/20",
};

export default function PayoutHistory({ payouts, formatDate, formatINR }) {
  return (
    <div>
      <h2 className="text-sm font-medium text-white/60 uppercase tracking-widest mb-4">
        Payout History
        <span className="ml-2 text-white/20 text-xs normal-case">auto-refreshes</span>
      </h2>
      <div className="space-y-2">
        {payouts.map((payout) => (
          <div key={payout.id} className="bg-white/3 border border-white/8 rounded-xl px-5 py-4">
            <div className="flex justify-between items-start mb-2">
              <span className="font-mono text-white font-medium">{formatINR(payout.amount_paise)}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColors[payout.status]}`}
              >
                {payout.status}
              </span>
            </div>
            <div className="text-xs text-white/30">
              {formatDate(payout.created_at)}
              {payout.failure_reason && (
                <span className="ml-2 text-red-400">{payout.failure_reason}</span>
              )}
            </div>
            <div className="text-xs text-white/20 font-mono mt-1 truncate">{payout.id}</div>
          </div>
        ))}
        {payouts.length === 0 && (
          <div className="text-white/20 text-sm text-center py-8">No payouts yet</div>
        )}
      </div>
    </div>
  );
}
