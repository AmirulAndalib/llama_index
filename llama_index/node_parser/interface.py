"""Node parser interface."""
from abc import ABC, abstractmethod
from typing import Any, List, Sequence

from llama_index.bridge.pydantic import Field
from llama_index.callbacks import CallbackManager, CBEventType, EventPayload
from llama_index.schema import (
    BaseNode,
    Document,
    NodeRelationship,
    RelatedNodeInfo,
    TransformComponent,
)
from llama_index.utils import get_tqdm_iterable


class NodeParser(TransformComponent, ABC):
    """Base interface for node parser."""

    include_metadata: bool = Field(
        default=True, description="Whether or not to consider metadata when splitting."
    )
    include_prev_next_rel: bool = Field(
        default=True, description="Include prev/next node relationships."
    )
    callback_manager: CallbackManager = Field(
        default_factory=CallbackManager, exclude=True
    )

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    def _parse_nodes(
        self,
        nodes: Sequence[BaseNode],
        show_progress: bool = False,
        **kwargs: Any,
    ) -> List[BaseNode]:
        ...

    def get_nodes_from_documents(
        self,
        documents: Sequence[Document],
        show_progress: bool = False,
        **kwargs: Any,
    ) -> List[BaseNode]:
        """Parse documents into nodes.

        Args:
            documents (Sequence[Document]): documents to parse
            show_progress (bool): whether to show progress bar

        """
        doc_id_to_document = {doc.doc_id: doc for doc in documents}

        with self.callback_manager.event(
            CBEventType.NODE_PARSING, payload={EventPayload.DOCUMENTS: documents}
        ) as event:
            nodes = self._parse_nodes(documents, show_progress=show_progress, **kwargs)

            if self.include_metadata:
                for node in nodes:
                    if node.ref_doc_id is not None:
                        node.metadata.update(
                            doc_id_to_document[node.ref_doc_id].metadata
                        )

            if self.include_prev_next_rel:
                for i, node in enumerate(nodes):
                    if i > 0:
                        node.relationships[NodeRelationship.PREVIOUS] = nodes[
                            i - 1
                        ].as_related_node_info()
                    if i < len(nodes) - 1:
                        node.relationships[NodeRelationship.NEXT] = nodes[
                            i + 1
                        ].as_related_node_info()

            event.on_end({EventPayload.NODES: nodes})

        return nodes

    def __call__(self, nodes: List[BaseNode], **kwargs: Any) -> List[BaseNode]:
        return self.get_nodes_from_documents(nodes, **kwargs)


class TextNodeParser(NodeParser):
    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        ...

    def split_texts(self, texts: List[str]) -> List[str]:
        nested_texts = [self.split_text(text) for text in texts]
        return [item for sublist in nested_texts for item in sublist]


class MetadataAwareTextNodeParser(TextNodeParser):
    @abstractmethod
    def split_text_metadata_aware(self, text: str, metadata_str: str) -> List[str]:
        ...

    def split_texts_metadata_aware(
        self, texts: List[str], metadata_strs: List[str]
    ) -> List[str]:
        if len(texts) != len(metadata_strs):
            raise ValueError("Texts and metadata_strs must have the same length")
        nested_texts = [
            self.split_text_metadata_aware(text, metadata)
            for text, metadata in zip(texts, metadata_strs)
        ]
        return [item for sublist in nested_texts for item in sublist]
