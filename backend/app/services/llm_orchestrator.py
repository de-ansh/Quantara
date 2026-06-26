"""
LLM Orchestrator using LangGraph State Machine

This module implements a structured LLM orchestration layer with:
- Strict system prompts with isolation
- JSON-only output enforcement
- Schema validation with retry logic
- Timeout protection
- Comprehensive logging
- No hallucinated numeric data allowed
"""
from typing import Any, TypedDict, Annotated, Optional
from enum import Enum
from datetime import datetime
import asyncio

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnalysisState(TypedDict):
    """State for the analysis workflow."""
    ticker: str
    raw_data: dict[str, Any]
    computed_metrics: dict[str, Any]
    risk_classification: dict[str, Any]
    structured_analysis: dict[str, Any]
    validation_errors: list[str]
    retry_count: int
    final_output: dict[str, Any] | None
    db: Optional[AsyncSession]
    openai_api_key: Optional[str]
    sec_user_agent: Optional[str]


class StructuredAnalysisSchema(BaseModel):
    """Pydantic schema for structured analysis output."""
    ticker: str = Field(..., description="Stock ticker symbol")
    summary: str = Field(..., description="Executive summary of analysis")
    key_insights: list[str] = Field(..., description="Key insights from analysis")
    strengths: list[str] = Field(..., description="Company strengths")
    weaknesses: list[str] = Field(..., description="Company weaknesses")
    opportunities: list[str] = Field(..., description="Market opportunities")
    threats: list[str] = Field(..., description="Market threats")
    confidence_score: float = Field(..., ge=0, le=100, description="Confidence in analysis")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "summary": "Strong fundamentals with premium valuation",
                "key_insights": ["Market leader in consumer electronics"],
                "strengths": ["Brand loyalty", "Ecosystem lock-in"],
                "weaknesses": ["High valuation", "China dependency"],
                "opportunities": ["Services growth", "AR/VR expansion"],
                "threats": ["Regulatory scrutiny", "Competition"],
                "confidence_score": 85.0
            }
        }


class LLMOrchestrator:
    """LLM orchestration using LangGraph state machine."""
    
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    
    def __init__(self):
        """Initialize the LLM orchestrator."""
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
            api_key=settings.openai_api_key,
            timeout=self.TIMEOUT_SECONDS,
        )
        
        # Build the state graph
        self.workflow = self._build_workflow()
        self.sec_provider = None  # Lazy init in retrieve_data if needed or here
    
    def _get_sec_provider(self, user_agent: Optional[str] = None):
        """Lazy initialization of SEC provider."""
        from app.providers.sec import SECProvider
        if user_agent:
            return SECProvider(user_agent=user_agent)
        if not self.sec_provider:
            self.sec_provider = SECProvider()
        return self.sec_provider

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AnalysisState)
        
        # Add nodes
        workflow.add_node("retrieve_data", self._retrieve_data)
        workflow.add_node("compute_metrics", self._compute_metrics)
        workflow.add_node("risk_classification", self._risk_classification)
        workflow.add_node("generate_analysis", self._generate_structured_analysis)
        workflow.add_node("validate_schema", self._validate_schema)
        workflow.add_node("store_result", self._store_result)
        
        # Define edges
        workflow.set_entry_point("retrieve_data")
        workflow.add_edge("retrieve_data", "compute_metrics")
        workflow.add_edge("compute_metrics", "risk_classification")
        workflow.add_edge("risk_classification", "generate_analysis")
        workflow.add_edge("generate_analysis", "validate_schema")
        
        # Conditional edge for validation
        workflow.add_conditional_edges(
            "validate_schema",
            self._should_retry,
            {
                "retry": "generate_analysis",
                "store": "store_result",
                "fail": END,
            }
        )
        
        workflow.add_edge("store_result", END)
        
        return workflow.compile()
    
    async def _retrieve_data(self, state: AnalysisState) -> AnalysisState:
        """Retrieve structured financial data."""
        logger.info(f"Retrieving data for {state['ticker']}")
        
        # Use SEC provider
        sec = self._get_sec_provider(state.get("sec_user_agent"))
        raw_facts = await sec.fetch_company_facts(state["ticker"])
        
        if raw_facts:
            metrics = sec.extract_metrics(raw_facts)
            latest = sec.get_latest_metrics(metrics)
            
            state["raw_data"] = {
                "ticker": state["ticker"],
                "financials": latest,
                "historical_metrics": metrics,
                "source": "SEC EDGAR",
            }
            logger.info(f"Successfully retrieved SEC data for {state['ticker']}")
        else:
            logger.warning(f"No SEC data retrieved for {state['ticker']}, using mock data")
            state["raw_data"] = {
                "ticker": state["ticker"],
                "financials": {},
                "transcripts": [],
                "news": [],
            }
        
        return state
    
    async def _compute_metrics(self, state: AnalysisState) -> AnalysisState:
        """Compute financial metrics."""
        ticker = state["ticker"]
        logger.info(f"Computing metrics for {ticker}")
        
        # 1. Fetch 1 year of daily historical data for the ticker and benchmark (^GSPC) from Yahoo Finance
        from app.providers.yahoo import YahooFinanceProvider
        yahoo = YahooFinanceProvider()
        
        from datetime import datetime, timedelta
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=365)
        start_date_str = start_dt.strftime("%Y-%m-%d")
        end_date_str = end_dt.strftime("%Y-%m-%d")
        
        try:
            df = await yahoo.get_historical_data(ticker, start_date=start_date_str, end_date=end_date_str)
            benchmark_df = await yahoo.get_historical_data("^GSPC", start_date=start_date_str, end_date=end_date_str)
            yahoo_metrics = yahoo.compute_metrics(df, benchmark_df)
        except Exception as e:
            logger.error(f"Error getting Yahoo Finance metrics for {ticker}: {e}")
            yahoo_metrics = {}
            
        # 2. Fetch yfinance info in a thread pool to avoid blocking
        import yfinance as yf
        def fetch_yf_info():
            try:
                s = yf.Ticker(ticker)
                return s.info
            except Exception as ex:
                logger.error(f"Error fetching yfinance info for {ticker}: {ex}")
                return {}
                
        info = await asyncio.to_thread(fetch_yf_info)
        
        # Store in raw_data for risk_classification node and Stock DB record
        state["raw_data"]["sector"] = info.get("sector")
        state["raw_data"]["pe_ratio"] = info.get("trailingPE") or info.get("forwardPE")
        state["raw_data"]["price_to_book"] = info.get("priceToBook")
        state["raw_data"]["price_to_sales"] = info.get("priceToSalesTrailing12Months")
        state["raw_data"]["market_cap"] = info.get("marketCap")
        state["raw_data"]["price"] = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        
        # 3. Compute metrics from SEC EDGAR data
        financials = state.get("raw_data", {}).get("financials", {})
        latest_rev = financials.get("revenue")
        latest_net_inc = financials.get("net_income")
        latest_assets = financials.get("total_assets")
        latest_debt = financials.get("total_debt")
        
        # Compute revenue growth from historical annual revenue facts
        rev_list = state.get("raw_data", {}).get("historical_metrics", {}).get("revenue", [])
        annual_revenues = [r for r in rev_list if r.get("form") == "10-K"]
        if len(annual_revenues) < 2:
            annual_revenues = rev_list
            
        revenue_growth = 0.0
        if len(annual_revenues) >= 2:
            latest_val = annual_revenues[-1]["val"]
            prev_val = annual_revenues[-2]["val"]
            if prev_val and prev_val != 0:
                revenue_growth = (latest_val - prev_val) / prev_val
                
        # Profit Margin
        profit_margin = 0.0
        if latest_rev and latest_rev != 0 and latest_net_inc is not None:
            profit_margin = latest_net_inc / latest_rev
            
        # Return on Equity (ROE)
        roe = 0.0
        if latest_net_inc is not None and latest_assets:
            equity = latest_assets - (latest_debt or 0)
            if equity <= 0:
                equity = latest_assets
            if equity != 0:
                roe = latest_net_inc / equity
                
        state["computed_metrics"] = {
            "revenue_growth": float(revenue_growth),
            "profit_margin": float(profit_margin),
            "roe": float(roe),
            "historical_volatility": yahoo_metrics.get("historical_volatility"),
            "max_drawdown": yahoo_metrics.get("max_drawdown"),
            "total_return": yahoo_metrics.get("total_return"),
            "beta": yahoo_metrics.get("beta"),
        }
        
        return state
    
    async def _risk_classification(self, state: AnalysisState) -> AnalysisState:
        """Classify risk using risk engine."""
        ticker = state["ticker"]
        logger.info(f"Classifying risk for {ticker}")
        
        from app.services.risk_engine import RiskEngine
        engine = RiskEngine()
        
        computed = state.get("computed_metrics", {})
        financials = state.get("raw_data", {}).get("financials", {})
        
        # Use computed or default metrics
        volatility = computed.get("historical_volatility")
        if volatility is None or volatility == 0.0:
            volatility = 0.25
        beta = computed.get("beta")
        if beta is None:
            beta = 1.0
            
        latest_assets = financials.get("total_assets") or 0.0
        latest_debt = financials.get("total_debt") or 0.0
        equity = latest_assets - latest_debt
        debt_to_equity = (latest_debt / equity) if equity > 0 else 0.0
        
        # Compute quarterly earnings volatility
        net_inc_list = [
            r["val"] for r in state.get("raw_data", {}).get("historical_metrics", {}).get("net_income", [])
        ]
        if len(net_inc_list) >= 2:
            import numpy as np
            mean_val = np.mean(np.abs(net_inc_list))
            earnings_volatility = float(np.std(net_inc_list) / mean_val) if mean_val > 0 else 0.0
        else:
            earnings_volatility = 0.15
            
        # Compute consecutive profitable quarters
        net_inc_quarters = [
            r for r in state.get("raw_data", {}).get("historical_metrics", {}).get("net_income", [])
            if r.get("form") == "10-Q"
        ]
        if not net_inc_quarters:
            net_inc_quarters = state.get("raw_data", {}).get("historical_metrics", {}).get("net_income", [])
            
        consecutive_profitable_quarters = 0
        for r in reversed(net_inc_quarters):
            if r["val"] > 0:
                consecutive_profitable_quarters += 1
            else:
                break
        if consecutive_profitable_quarters == 0 and any(r["val"] > 0 for r in net_inc_quarters):
            consecutive_profitable_quarters = 4
            
        # Get sector & valuation ratios
        raw_data = state.get("raw_data", {})
        sector = raw_data.get("sector")
        
        # Fallback sector check from database
        db = state.get("db")
        if (not sector or sector == "Unknown") and db is not None:
            from app.models.stock import Stock
            from sqlalchemy import select
            stmt = select(Stock).where(Stock.ticker == ticker)
            res = await db.execute(stmt)
            stock = res.scalar_one_or_none()
            if stock and stock.sector:
                sector = stock.sector
        if not sector:
            sector = "Technology"
            
        pe_ratio = raw_data.get("pe_ratio")
        price_to_book = raw_data.get("price_to_book")
        price_to_sales = raw_data.get("price_to_sales")
        
        analysis = engine.analyze_stock_risk(
            ticker=ticker,
            historical_volatility=volatility,
            beta=beta,
            debt_to_equity=debt_to_equity,
            earnings_volatility=earnings_volatility,
            consecutive_profitable_quarters=consecutive_profitable_quarters,
            sector=sector,
            pe_ratio=pe_ratio,
            price_to_book=price_to_book,
            price_to_sales=price_to_sales,
        )
        
        state["risk_classification"] = {
            "risk_score": float(analysis.overall_risk_score),
            "risk_level": analysis.risk_level.value,
            "components": {
                "volatility_score": float(analysis.components.volatility_score),
                "beta_score": float(analysis.components.beta_score),
                "leverage_score": float(analysis.components.leverage_score),
                "earnings_stability_score": float(analysis.components.earnings_stability_score),
                "sector_risk_score": float(analysis.components.sector_risk_score),
                "valuation_risk_score": float(analysis.components.valuation_risk_score),
            },
            "risk_band": analysis.risk_band,
            "explanation": analysis.explanation,
        }
        
        return state
    
    def _generate_structured_analysis(self, state: AnalysisState) -> AnalysisState:
        """Generate structured analysis using LLM."""
        logger.info(f"Generating analysis for {state['ticker']}")
        
        # Build strict system prompt
        system_prompt = """You are a financial analyst AI. Your task is to analyze the provided data and generate a structured analysis.

CRITICAL RULES:
1. Output ONLY valid JSON matching the exact schema provided
2. Do NOT hallucinate or invent numeric data
3. Base all insights on the provided data only
4. If data is missing, acknowledge it in your analysis
5. Provide confidence scores based on data completeness

Output must be valid JSON matching this schema:
{
    "ticker": "string",
    "summary": "string",
    "key_insights": ["string"],
    "strengths": ["string"],
    "weaknesses": ["string"],
    "opportunities": ["string"],
    "threats": ["string"],
    "confidence_score": float (0-100)
}"""
        
        # Build context from state
        context = f"""
Ticker: {state['ticker']}

Raw Data:
{state.get('raw_data', {})}

Computed Metrics:
{state.get('computed_metrics', {})}

Risk Classification:
{state.get('risk_classification', {})}

Generate a structured analysis based on this data.
"""
        
        try:
            # Call LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context),
            ]
            
            llm = self.llm
            if state.get("openai_api_key"):
                llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=settings.openai_temperature,
                    max_tokens=settings.openai_max_tokens,
                    api_key=state["openai_api_key"],
                    timeout=self.TIMEOUT_SECONDS,
                )
            response = llm.invoke(messages)
            
            # Log prompt and response
            logger.info(
                "LLM invocation",
                extra={
                    "ticker": state["ticker"],
                    "prompt_length": len(context),
                    "response_length": len(response.content),
                }
            )
            
            # Parse JSON response
            import json
            analysis = json.loads(response.content)
            state["structured_analysis"] = analysis
            
        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            state["validation_errors"].append(str(e))
        
        return state
    
    def _validate_schema(self, state: AnalysisState) -> AnalysisState:
        """Validate output against Pydantic schema."""
        logger.info(f"Validating schema for {state['ticker']}")
        
        try:
            # Validate using Pydantic
            validated = StructuredAnalysisSchema(**state["structured_analysis"])
            state["final_output"] = validated.model_dump()
            state["validation_errors"] = []
            
            logger.info(f"Schema validation successful for {state['ticker']}")
            
        except Exception as e:
            logger.warning(f"Schema validation failed: {e}")
            state["validation_errors"].append(str(e))
            state["retry_count"] = state.get("retry_count", 0) + 1
        
        return state
    
    def _should_retry(self, state: AnalysisState) -> str:
        """Determine if we should retry generation."""
        if not state["validation_errors"]:
            return "store"
        
        if state.get("retry_count", 0) >= self.MAX_RETRIES:
            logger.error(f"Max retries exceeded for {state['ticker']}")
            return "fail"
        
        logger.info(f"Retrying generation for {state['ticker']}")
        return "retry"
    
    async def _store_result(self, state: AnalysisState) -> AnalysisState:
        """Store the final result."""
        ticker = state["ticker"]
        logger.info(f"Storing result for {ticker}")
        
        db = state.get("db")
        if db is not None:
            from app.models.research import ResearchReport
            from app.models.stock import Stock
            from sqlalchemy import select
            
            # Upsert Stock record
            stmt = select(Stock).where(Stock.ticker == ticker)
            result = await db.execute(stmt)
            stock = result.scalar_one_or_none()
            
            risk_classification = state.get("risk_classification", {})
            risk_score = risk_classification.get("risk_score")
            research_score = state.get("final_output", {}).get("confidence_score")
            
            sector = state.get("raw_data", {}).get("sector") or (stock.sector if stock else "Technology")
            
            # Extract additional fields
            pe_ratio = state.get("raw_data", {}).get("pe_ratio")
            beta = state.get("computed_metrics", {}).get("beta")
            raw_mcap = state.get("raw_data", {}).get("market_cap")
            raw_price = state.get("raw_data", {}).get("price")
            
            def format_market_cap(val):
                if not val: return "N/A"
                try:
                    val = float(val)
                    if val >= 1e12: return f"{val / 1e12:.2f}T"
                    elif val >= 1e9: return f"{val / 1e9:.2f}B"
                    elif val >= 1e6: return f"{val / 1e6:.2f}M"
                    return f"{val:,.0f}"
                except Exception: return "N/A"
                
            def format_price(val):
                if not val: return "N/A"
                try: return f"${float(val):,.2f}"
                except Exception: return "N/A"
                
            market_cap_str = format_market_cap(raw_mcap)
            price_str = format_price(raw_price)
            
            # Deterministic Alpha Projection
            research_val = research_score or 50.0
            risk_val = risk_score or 50.0
            alpha_val = (research_val * 0.2) - (risk_val * 0.05)
            alpha_str = f"{'+' if alpha_val >= 0 else ''}{alpha_val:.1f}%"
            
            status = "neutral"
            if alpha_val > 5.0:
                status = "up"
            elif alpha_val < -2.0:
                status = "down"

            if not stock:
                stock = Stock(
                    ticker=ticker,
                    name=ticker,
                    sector=sector,
                    risk_score=risk_score,
                    research_score=research_score,
                    pe_ratio=pe_ratio,
                    beta=beta,
                    market_cap=market_cap_str,
                    price=price_str,
                    alpha_projection=alpha_str,
                    status=status
                )
                db.add(stock)
            else:
                stock.risk_score = risk_score
                stock.research_score = research_score
                if sector and sector != "Unknown":
                    stock.sector = sector
                stock.pe_ratio = pe_ratio
                stock.beta = beta
                stock.market_cap = market_cap_str
                stock.price = price_str
                stock.alpha_projection = alpha_str
                stock.status = status
            
            await db.commit()
            
            # Upsert ResearchReport record
            final_output = state.get("final_output")
            if final_output:
                stmt_report = select(ResearchReport).where(ResearchReport.ticker == ticker)
                result_report = await db.execute(stmt_report)
                report = result_report.scalar_one_or_none()
                
                if report:
                    report.structured_json = final_output
                    report.confidence_score = final_output.get("confidence_score", 0.0)
                    report.summary = final_output.get("summary")
                    report.version += 1
                    report.updated_at = datetime.utcnow()
                else:
                    report = ResearchReport(
                        ticker=ticker,
                        structured_json=final_output,
                        confidence_score=final_output.get("confidence_score", 0.0),
                        summary=final_output.get("summary"),
                        version=1,
                    )
                    db.add(report)
                
                await db.commit()
                logger.info(f"Successfully stored research report for {ticker} in database")
                
        return state
    
    async def analyze_stock(
        self,
        ticker: str,
        db: Optional[AsyncSession] = None,
        openai_api_key: Optional[str] = None,
        sec_user_agent: Optional[str] = None,
    ) -> dict[str, Any] | None:
        """
        Run complete analysis workflow for a stock.
        
        Args:
            ticker: Stock ticker symbol
            db: Database session
            openai_api_key: Optional OpenAI API key override
            sec_user_agent: Optional SEC User Agent override
        
        Returns:
            Structured analysis or None if failed
        """
        logger.info(f"Starting analysis workflow for {ticker}")
        
        # Initialize state
        initial_state: AnalysisState = {
            "ticker": ticker,
            "raw_data": {},
            "computed_metrics": {},
            "risk_classification": {},
            "structured_analysis": {},
            "validation_errors": [],
            "retry_count": 0,
            "final_output": None,
            "db": db,
            "openai_api_key": openai_api_key,
            "sec_user_agent": sec_user_agent,
        }
        
        try:
            # Run workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            if final_state["final_output"]:
                logger.info(f"Analysis workflow completed successfully for {ticker}")
                return final_state["final_output"]
            else:
                logger.error(f"Analysis workflow failed for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"Analysis workflow error for {ticker}: {e}")
            return None
