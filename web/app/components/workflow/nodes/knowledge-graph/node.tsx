import type { FC } from 'react'
import React from 'react'
import type { KnowledgeGraphNodeType } from './types'
import type { NodeProps } from '@/app/components/workflow/types'

const Node: FC<NodeProps<KnowledgeGraphNodeType>> = () => {
  return (
    // No summary content
    <div></div>
  )
}

export default React.memo(Node)
