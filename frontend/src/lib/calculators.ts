/** Investment calculators: plain compounding maths, no data or API. */

export interface CalcField { key: string; label: string; initial: number }
export interface CalcRow { label: string; value: string }
export interface Calculator {
    id: string
    name: string
    fields: CalcField[]
    compute: (v: Record<string, number>) => CalcRow[]
    note?: string  // assumptions shown under the result
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
    {
        id: "income-tax", name: "Income tax",
        fields: [
            { key: "salary", label: "Salary for the year (₹)", initial: 1500000 },
            { key: "other", label: "Other income: interest, rent, etc. (₹)", initial: 0 },
            { key: "deductions", label: "Old-regime deductions: 80C, 80D, HRA, home loan (₹)", initial: 200000 },
        ],
        compute: ({ salary, other, deductions }) => {
            const newTax = regimeTax(Math.max(0, salary - NEW_REGIME.standardDeduction) + other, NEW_REGIME)
            const oldTax = regimeTax(Math.max(0, salary - OLD_REGIME.standardDeduction - deductions) + other, OLD_REGIME)
            const better = newTax <= oldTax ? "New regime" : "Old regime"
            const gross = salary + other
            return [
                { label: "Better for you", value: newTax === oldTax ? "Either (same tax)" : `${better}, saves ${inr(Math.abs(newTax - oldTax))}` },
                { label: "Tax under the new regime", value: inr(newTax) },
                { label: "Tax under the old regime", value: inr(oldTax) },
                { label: "Effective rate (better regime)", value: gross ? `${((Math.min(newTax, oldTax) / gross) * 100).toFixed(2)}%` : "0%" },
            ]
        },
        note: "Slabs for FY 2025-26 and FY 2026-27 (set in Budget 2025; Budget 2026 left them unchanged), including the 4% cess, standard deduction and the ₹12 lakh rebate. Surcharge applies above ₹50 lakh without marginal relief. Check for later Budget changes before filing.",
    },
    {
        id: "capital-gains", name: "Capital gains",
        fields: [
            { key: "buy", label: "Bought for (₹)", initial: 200000 },
            { key: "sell", label: "Sold for (₹)", initial: 500000 },
            { key: "months", label: "Months held", initial: 18 },
            { key: "usedExemption", label: "Long-term gains already booked this year (₹)", initial: 0 },
        ],
        compute: ({ buy, sell, months, usedExemption }) => {
            const gain = sell - buy
            const longTerm = months > 12
            const exemptLeft = longTerm ? Math.max(0, LTCG_EXEMPTION - usedExemption) : 0
            const taxable = Math.max(0, gain - exemptLeft)
            const tax = taxable * (longTerm ? LTCG_RATE : STCG_RATE) * (1 + CESS)
            return [
                { label: "Tax", value: inr(tax) },
                { label: gain >= 0 ? "Gain" : "Loss", value: `${inr(Math.abs(gain))} (${longTerm ? "long-term, 12.5%" : "short-term, 20%"})` },
                { label: "Taxable after the ₹1.25 lakh exemption", value: inr(taxable) },
                { label: "You keep", value: inr(sell - tax) },
            ]
        },
        note: "Listed shares and equity mutual funds sold on or after 23 July 2024: short-term (12 months or less) at 20%, long-term at 12.5% above ₹1.25 lakh of long-term gains a year, plus 4% cess. Unchanged by Budget 2026. Ignores surcharge, the 2018 grandfathering rule and share buybacks (taxed as capital gains from FY 2026-27).",
    },
    {
        id: "hra", name: "HRA exemption",
        fields: [
            { key: "basic", label: "Basic salary + DA for the year (₹)", initial: 600000 },
            { key: "hra", label: "HRA received for the year (₹)", initial: 240000 },
            { key: "rent", label: "Rent paid for the year (₹)", initial: 240000 },
            { key: "metro", label: "Metro city? (1 = Delhi, Mumbai, Kolkata, Chennai; 0 = other)", initial: 1 },
        ],
        compute: ({ basic, hra, rent, metro }) => {
            const exempt = Math.max(0, Math.min(hra, rent - 0.1 * basic, (metro === 1 ? 0.5 : 0.4) * basic))
            return [
                { label: "Tax-free HRA", value: inr(exempt) },
                { label: "Taxable HRA", value: inr(hra - exempt) },
                { label: "Limits compared", value: `HRA ${inr(hra)} · rent − 10% of basic ${inr(Math.max(0, rent - 0.1 * basic))} · ${metro === 1 ? "50" : "40"}% of basic ${inr((metro === 1 ? 0.5 : 0.4) * basic)}` },
            ]
        },
        note: "The exemption is the lowest of the three limits. Only the old tax regime allows it.",
    },
    {
        id: "epf", name: "EPF",
        fields: [
            { key: "basic", label: "Monthly basic + DA (₹)", initial: 50000 },
            { key: "balance", label: "Current EPF balance (₹)", initial: 0 },
            { key: "growth", label: "Salary growth (% a year)", initial: 5 },
            { key: "rate", label: "EPF interest (% a year)", initial: 8.25 },
            { key: "years", label: "Years", initial: 20 },
        ],
        compute: ({ basic, balance, growth, rate, years }) => {
            let total = balance, contributed = 0, pay = basic
            for (let y = 0; y < years; y++) {
                let interest = 0
                for (let m = 0; m < 12; m++) {
                    const monthly = pay * EPF_SHARE
                    total += monthly
                    contributed += monthly
                    interest += total * rate / 1200  // on each month's closing balance, credited at year end
                }
                total += interest
                pay *= 1 + growth / 100
            }
            return [
                { label: "EPF balance", value: inr(total) },
                { label: "Contributed (you + employer)", value: inr(contributed) },
                { label: "Interest earned", value: inr(total - balance - contributed) },
            ]
        },
        note: "12% from you and 3.67% from your employer go to EPF (the employer's other 8.33% goes to the pension scheme). 8.25% was the rate for FY 2024-25 and FY 2025-26.",
    },
]

const CESS = 0.04
const STCG_RATE = 0.2
const LTCG_RATE = 0.125
const LTCG_EXEMPTION = 125000
const EPF_SHARE = 0.12 + 0.0367

interface Regime {
    standardDeduction: number
    slabs: [upTo: number, rate: number][]
    rebateLimit: number  // section 87A: no tax up to this taxable income
    surcharge: [above: number, rate: number][]
}

const NEW_REGIME: Regime = {
    standardDeduction: 75000,
    slabs: [[400000, 0], [800000, 0.05], [1200000, 0.1], [1600000, 0.15], [2000000, 0.2], [2400000, 0.25], [Infinity, 0.3]],
    rebateLimit: 1200000,
    surcharge: [[20000000, 0.25], [10000000, 0.15], [5000000, 0.1]],
}
const OLD_REGIME: Regime = {
    standardDeduction: 50000,
    slabs: [[250000, 0], [500000, 0.05], [1000000, 0.2], [Infinity, 0.3]],
    rebateLimit: 500000,
    surcharge: [[50000000, 0.37], [20000000, 0.25], [10000000, 0.15], [5000000, 0.1]],
}

/** Tax with cess on a taxable income, including the 87A rebate and its marginal relief. */
export function regimeTax(taxable: number, regime: Regime): number {
    let tax = 0, lower = 0
    for (const [upTo, rate] of regime.slabs) {
        if (taxable > lower) tax += (Math.min(taxable, upTo) - lower) * rate
        lower = upTo
    }
    if (taxable <= regime.rebateLimit) tax = 0
    else tax = Math.min(tax, taxable - regime.rebateLimit)  // marginal relief: never more than the income above the limit
    const surcharge = regime.surcharge.find(([above]) => taxable > above)?.[1] ?? 0
    return Math.round(tax * (1 + surcharge) * (1 + CESS))
}

/** Results for valid inputs, or null when a value is missing, negative or makes the maths meaningless. */
export function calculate(calc: Calculator, values: Record<string, number>): CalcRow[] | null {
    if (calc.fields.some(f => !Number.isFinite(values[f.key]) || values[f.key] < 0)) return null
    if (values.years === 0 || (calc.id === "cagr" && values.start === 0)) return null
    if (calc.id === "retirement" && !(values.age < values.retireAge && values.retireAge < values.lifeAge)) return null
    if (calc.id === "hra" && values.metro !== 0 && values.metro !== 1) return null
    return calc.compute(values)
}
