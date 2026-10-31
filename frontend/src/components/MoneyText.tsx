const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });

// Display only (rule 5): `value` is the API's money string; never do arithmetic with the parsed number.
export default function MoneyText({ value }: { value: string | null | undefined }) {
  if (value === null || value === undefined || value === "") return <>—</>;
  return <span className="tabular-nums">{inr.format(Number(value))}</span>;
}
