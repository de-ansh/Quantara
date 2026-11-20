/** Risk scores run 0-100, higher is riskier; a word makes the number readable. */
export const riskWord = (risk: number | null | undefined) =>
    risk === null || risk === undefined || !Number.isFinite(risk) ? "—" : risk < 35 ? "Low" : risk < 65 ? "Medium" : "High"
