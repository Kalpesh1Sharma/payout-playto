export default function BalanceCard({ title, value, valueClassName = "text-white" }) {
  return (
    <div className="bg-white/3 border border-white/8 rounded-xl p-5">
      <div className="text-white/40 text-xs uppercase tracking-widest mb-2">{title}</div>
      <div className={`text-3xl font-semibold font-mono ${valueClassName}`}>{value}</div>
    </div>
  );
}
