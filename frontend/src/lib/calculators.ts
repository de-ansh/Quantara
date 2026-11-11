/** Investment calculators: plain compounding maths, no data or API. */

export interface CalcField { key: string; label: string; initial: number }
export interface CalcRow { label: string; value: string }
export interface Calculator {
    id: string
    name: string
    fields: CalcField[]
    compute: (v: Record<string, number>) => CalcRow[]
}

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`

/** Future value of `n` equal payments made at the start of each period. */
const annuityDue = (payment: number, rate: number, n: number) =>
    rate === 0 ? payment * n : payment * ((Math.pow(1 + rate, n) - 1) / rate) * (1 + rate)

export const CALCULATORS: Calculator[] = [
    {
        id: "sip", name: "SIP",
        fields: [
            { key: "amount", label: "Monthly investment (₹)", initial: 10000 },
            { key: "rate", label: "Expected return (% a year)", initial: 12 },
            { key: "years", label: "Years", initial: 10 },
        ],
        compute: ({ amount, rate, years }) => {
            const value = annuityDue(amount, rate / 1200, years * 12)
            const invested = amount * years * 12
            return [{ label: "Maturity value", value: inr(value) }, { label: "Invested", value: inr(invested) }, { label: "Gain", value: inr(value - invested) }]
        },
    },
    {
        id: "lumpsum", name: "Lumpsum",
        fields: [
            { key: "amount", label: "Investment (₹)", initial: 100000 },
            { key: "rate", label: "Expected return (% a year)", initial: 12 },
            { key: "years", label: "Years", initial: 10 },
        ],
        compute: ({ amount, rate, years }) => {
            const value = amount * Math.pow(1 + rate / 100, years)
            return [{ label: "Maturity value", value: inr(value) }, { label: "Invested", value: inr(amount) }, { label: "Gain", value: inr(value - amount) }]
        },
    },
    {
        id: "swp", name: "SWP",
        fields: [
            { key: "corpus", label: "Starting corpus (₹)", initial: 5000000 },
            { key: "withdrawal", label: "Monthly withdrawal (₹)", initial: 40000 },
            { key: "rate", label: "Expected return (% a year)", initial: 8 },
            { key: "years", label: "Years", initial: 20 },
        ],
        compute: ({ corpus, withdrawal, rate, years }) => {
            let balance = corpus, withdrawn = 0, months = 0
            while (months < years * 12 && balance >= withdrawal && withdrawal > 0) {
                balance = (balance - withdrawal) * (1 + rate / 1200)
                withdrawn += withdrawal
                months++
            }
            return [
                { label: "Balance at the end", value: inr(balance) },
                { label: "Total withdrawn", value: inr(withdrawn) },
                { label: "Money lasts", value: months >= years * 12 ? `The full ${years} years` : `${Math.floor(months / 12)} years ${months % 12} months` },
            ]
        },
    },
    {
        id: "fd", name: "Fixed deposit",
        fields: [
            { key: "amount", label: "Deposit (₹)", initial: 100000 },
            { key: "rate", label: "Interest (% a year)", initial: 7 },
            { key: "years", label: "Years", initial: 5 },
        ],
        // Indian banks compound fixed deposits quarterly
        compute: ({ amount, rate, years }) => {
            const value = amount * Math.pow(1 + rate / 400, years * 4)
            return [{ label: "Maturity value", value: inr(value) }, { label: "Interest earned", value: inr(value - amount) }]
        },
    },
    {
        id: "ppf", name: "PPF",
        fields: [
            { key: "amount", label: "Yearly deposit (₹)", initial: 150000 },
            { key: "rate", label: "Interest (% a year)", initial: 7.1 },
            { key: "years", label: "Years", initial: 15 },
        ],
        compute: ({ amount, rate, years }) => {
            const value = annuityDue(amount, rate / 100, years)
            const invested = amount * years
            return [{ label: "Maturity value", value: inr(value) }, { label: "Invested", value: inr(invested) }, { label: "Interest earned", value: inr(value - invested) }]
        },
    },
    {
        id: "cagr", name: "CAGR",
        fields: [
            { key: "start", label: "Starting value (₹)", initial: 100000 },
            { key: "end", label: "Ending value (₹)", initial: 250000 },
            { key: "years", label: "Years", initial: 5 },
        ],
        compute: ({ start, end, years }) => [
            { label: "CAGR", value: `${((Math.pow(end / start, 1 / years) - 1) * 100).toFixed(2)}%` },
            { label: "Absolute return", value: `${((end / start - 1) * 100).toFixed(2)}%` },
        ],
    },
    {
        id: "retirement", name: "Retirement",
        fields: [
            { key: "age", label: "Current age", initial: 30 },
            { key: "retireAge", label: "Retirement age", initial: 60 },
            { key: "lifeAge", label: "Plan until age", initial: 85 },
            { key: "expense", label: "Monthly expenses today (₹)", initial: 50000 },
            { key: "inflation", label: "Inflation (% a year)", initial: 6 },
            { key: "preReturn", label: "Return before retiring (% a year)", initial: 12 },
            { key: "postReturn", label: "Return after retiring (% a year)", initial: 8 },
        ],
        compute: ({ age, retireAge, lifeAge, expense, inflation, preReturn, postReturn }) => {
            const expenseAtRetirement = expense * Math.pow(1 + inflation / 100, retireAge - age)
            const months = (lifeAge - retireAge) * 12
            const realMonthly = Math.pow((1 + postReturn / 100) / (1 + inflation / 100), 1 / 12) - 1
            const corpus = realMonthly === 0
                ? expenseAtRetirement * months
                : expenseAtRetirement * ((1 - Math.pow(1 + realMonthly, -months)) / realMonthly) * (1 + realMonthly)
            const sip = corpus / annuityDue(1, preReturn / 1200, (retireAge - age) * 12)
            return [
                { label: "Corpus needed at retirement", value: inr(corpus) },
                { label: "Monthly SIP to get there", value: inr(sip) },
                { label: "Monthly expenses at retirement", value: inr(expenseAtRetirement) },
            ]
        },
    },
]

/** Results for valid inputs, or null when a value is missing, negative or makes the maths meaningless. */
export function calculate(calc: Calculator, values: Record<string, number>): CalcRow[] | null {
    if (calc.fields.some(f => !Number.isFinite(values[f.key]) || values[f.key] < 0)) return null
    if (values.years === 0 || (calc.id === "cagr" && values.start === 0)) return null
    if (calc.id === "retirement" && !(values.age < values.retireAge && values.retireAge < values.lifeAge)) return null
    return calc.compute(values)
}
