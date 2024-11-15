from typing import Literal, Optional

from pydantic import BaseModel

from core.helper.code_executor.code_executor import CodeLanguage
from core.workflow.entities.base_node_data_entities import BaseNodeData
from core.workflow.entities.variable_entities import VariableSelector


class KnowledgeGraphNodeData(BaseNodeData):
    """
    KnowledgeGraph Node Data.
    """
    class Output(BaseModel):
        type: Literal['string', 'number', 'object', 'array[string]', 'array[number]', 'array[object]']
        children: Optional[dict[str, 'Output']] = None

    class Dependency(BaseModel):
        name: str
        version: str

    variables: list[VariableSelector]
    code_language: Literal[CodeLanguage.PYTHON3, CodeLanguage.JAVASCRIPT]
    code: str
    outputs: dict[str, Output]
    dependencies: Optional[list[Dependency]] = None