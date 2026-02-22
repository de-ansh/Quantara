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
from typing import Any, TypedDict, Annotated
from enum import Enum

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

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
    
    def _get_sec_provider(self):
        """Lazy initialization of SEC provider."""
        from app.providers.sec import SECProvider
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
        sec = self._get_sec_provider()
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
    
    def _compute_metrics(self, state: AnalysisState) -> AnalysisState:
        """Compute financial metrics."""
        logger.info(f"Computing metrics for {state['ticker']}")
        
        # TODO: Implement actual metric computation
        state["computed_metrics"] = {
            "revenue_growth": 0.0,
            "profit_margin": 0.0,
            "roe": 0.0,
        }
        
        return state
    
    def _risk_classification(self, state: AnalysisState) -> AnalysisState:
        """Classify risk using risk engine."""
        logger.info(f"Classifying risk for {state['ticker']}")
        
        # TODO: Call risk engine
        state["risk_classification"] = {
            "risk_score": 50.0,
            "risk_level": "Moderate",
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
            
            response = self.llm.invoke(messages)
            
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
    
    def _store_result(self, state: AnalysisState) -> AnalysisState:
        """Store the final result."""
        logger.info(f"Storing result for {state['ticker']}")
        
        # TODO: Store in database
        
        return state
    
    async def analyze_stock(self, ticker: str) -> dict[str, Any] | None:
        """
        Run complete analysis workflow for a stock.
        
        Args:
            ticker: Stock ticker symbol
        
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
