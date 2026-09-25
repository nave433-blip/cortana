import math

def chunk_task(task: str, num_chunks: int) -> list:
    """Splits a large task into smaller, manageable chunks."""
    if num_chunks <= 1:
        return [task]
    
    # Simple character-based splitting, can be improved to sentence/logical block splitting
    chunk_size = math.ceil(len(task) / num_chunks)
    chunks = [task[i:i+chunk_size] for i in range(0, len(task), chunk_size)]
    return chunks

def aggregate_results(results: list) -> str:
    """Aggregates chunk results into a final coherent answer."""
    return "\n\n".join(results)
