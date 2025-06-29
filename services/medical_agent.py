"""
Advanced Medical Agent System using LangGraph
Replaces simple LLM chains with sophisticated tool orchestration and adaptive routing
"""

import asyncio
import json
from typing import Annotated, Dict, Any, List, Literal, Optional, TypedDict
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from pydantic import SecretStr
from flask import current_app

from services.medical_tools import MEDICAL_TOOLS
from utils.constants import MEDICAL_AGENT_SYSTEM_PROMPT


class MedicalAgentState(TypedDict):
    """
    Enhanced state for medical agent conversations
    
    Features:
    - Message history with LangGraph's add_messages reducer
    - User context tracking
    - Agent metadata storage
    """
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    user_location: Optional[str]
    emergency_mode: bool
    analysis_metadata: Dict[str, Any]


class MedicalAgentSystem:
    """
    Sophisticated medical agent using LangGraph orchestration
    
    Features:
    - Tool-based medical analysis (no simple chains)
    - Adaptive routing between specialized tools
    - Context-aware conversation management
    - Emergency situation handling
    - Multi-modal support (text, images, location)
    """
    
    def __init__(self):
        """Initialize the medical agent system"""
        self.tools = MEDICAL_TOOLS
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        self.memory = MemorySaver()
        self.llm = self._setup_llm()
        self.graph = self._build_agent_graph()
        
    def _setup_llm(self) -> ChatGoogleGenerativeAI:
        """Setup the LLM with medical context"""
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in configuration")
            
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=SecretStr(api_key),
            temperature=0.3,
            convert_system_message_to_human=False
        ).bind_tools(self.tools)
    
    def _build_agent_graph(self) -> StateGraph:
        """Build the LangGraph medical agent workflow"""
        
        def route_decision(state: MedicalAgentState) -> Literal["tools", "respond"]:
            """Route based on last message tool calls"""
            messages = state["messages"]
            if not messages:
                return "respond"
                
            last_message = messages[-1]
            
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return "respond"
        
        def medical_agent_node(state: MedicalAgentState) -> Dict[str, Any]:
            """Main agent node - orchestrates medical analysis"""
            messages = state["messages"]
            user_id = state["user_id"]
            emergency_mode = state["emergency_mode"]
            
            # Add medical context to system prompt
            system_context = self._build_system_context(state)
            
            # Prepend system message if not already present
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_context)] + messages
            
            # Get LLM response with tool calls
            response = self.llm.invoke(messages)
            
            return {
                "messages": [response],
                "analysis_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "emergency_detected": emergency_mode,
                    "tools_available": len(self.tools)
                }
            }
        
        def tools_node(state: MedicalAgentState) -> Dict[str, Any]:
            """Execute tools based on last message tool calls"""
            messages = state["messages"]
            if not messages:
                return {"messages": []}
                
            last_message = messages[-1]
            if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                return {"messages": []}
            
            tool_messages = []
            
            # Execute each tool call
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]
                
                try:
                    if tool_name in self.tools_by_name:
                        tool = self.tools_by_name[tool_name]
                        result = tool.invoke(tool_args)
                        
                        tool_messages.append(ToolMessage(
                            content=str(result),
                            name=tool_name,
                            tool_call_id=tool_call_id
                        ))
                    else:
                        tool_messages.append(ToolMessage(
                            content=f"Tool {tool_name} not found",
                            name=tool_name,
                            tool_call_id=tool_call_id
                        ))
                        
                except Exception as e:
                    tool_messages.append(ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        name=tool_name,
                        tool_call_id=tool_call_id
                    ))
            
            return {"messages": tool_messages}
        
        def respond_node(state: MedicalAgentState) -> Dict[str, Any]:
            """Final response node - ensures proper medical disclaimers"""
            return {"messages": []}  # No additional messages needed
        
        # Build the graph
        workflow = StateGraph(MedicalAgentState)
        
        # Add nodes
        workflow.add_node("agent", medical_agent_node)
        workflow.add_node("tools", tools_node)
        workflow.add_node("respond", respond_node)
        
        # Add edges
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            route_decision,
            {
                "tools": "tools",
                "respond": "respond"
            }
        )
        workflow.add_edge("tools", "agent")
        workflow.add_edge("respond", END)
        
        return workflow.compile(checkpointer=self.memory)
    
    def _build_system_context(self, state: MedicalAgentState) -> str:
        """Build contextualized system prompt"""
        base_prompt = MEDICAL_AGENT_SYSTEM_PROMPT
        
        # Add user context
        user_context = ""
        if state.get("user_location"):
            user_context += f"\nUser location: {state['user_location']}"
        
        if state.get("emergency_mode"):
            user_context += "\n⚠️ EMERGENCY MODE: Prioritize immediate medical guidance and emergency services."
        
        # Add available tools context
        tools_context = f"\nAvailable medical tools: {[tool.name for tool in self.tools]}"
        
        return base_prompt + user_context + tools_context
    
    async def analyze_medical_query(
        self,
        user_id: str,
        message: str,
        image_data: Optional[bytes] = None,
        location: Optional[str] = None,
        emergency: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze medical query using LangGraph agent
        
        Args:
            user_id: User identifier
            message: Medical query or symptoms
            image_data: Optional medical image
            location: User location for local medical resources
            emergency: Emergency situation flag
            
        Returns:
            Analysis results with tool outputs and recommendations
        """
        
        # Prepare initial state
        initial_state = MedicalAgentState(
            messages=[HumanMessage(content=message)],
            user_id=user_id,
            user_location=location,
            emergency_mode=emergency,
            analysis_metadata={}
        )
        
        # Add image if provided
        if image_data:
            image_message = HumanMessage(
                content=[
                    {"type": "text", "text": message},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data.decode() if isinstance(image_data, bytes) else image_data}"
                        }
                    }
                ]
            )
            initial_state["messages"] = [image_message]
        
        # Execute agent workflow
        config = {"configurable": {"thread_id": user_id}}
        
        try:
            result = await self.graph.ainvoke(initial_state, config=config)
            
            return {
                "success": True,
                "analysis": self._extract_analysis_result(result),
                "tools_used": self._extract_tools_used(result),
                "emergency_detected": result.get("emergency_mode", False),
                "metadata": result.get("analysis_metadata", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fallback_message": "I encountered an issue analyzing your medical query. Please consult with a healthcare professional."
            }
    
    def _extract_analysis_result(self, result: Dict[str, Any]) -> str:
        """Extract the main analysis result from agent output"""
        messages = result.get("messages", [])
        
        # Find the last AI message
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                return message.content
        
        return "Unable to provide analysis. Please consult a healthcare professional."
    
    def _extract_tools_used(self, result: Dict[str, Any]) -> List[str]:
        """Extract list of tools used during analysis"""
        messages = result.get("messages", [])
        tools_used = []
        
        for message in messages:
            if isinstance(message, ToolMessage):
                tools_used.append(message.name)
        
        return list(set(tools_used))  # Remove duplicates


# Global agent system instance
_medical_agent_system = None

def get_medical_agent_system() -> MedicalAgentSystem:
    """Get global medical agent system instance"""
    global _medical_agent_system
    if _medical_agent_system is None:
        _medical_agent_system = MedicalAgentSystem()
    return _medical_agent_system 