"""Tools available to Athena."""
from typing import Optional, List
import urllib.parse


async def gcp_assistant(
    query: str,
    category: str = "general",
    service_name: Optional[str] = None
) -> dict:
    """Query Google Cloud Platform (GCP) real-time information, documentation, service status, pricing, or troubleshooting.

    Args:
        query: The specific GCP question, error message, or architecture query.
        category: Category of request ('pricing', 'quotas', 'troubleshooting', 'documentation', 'best_practices').
        service_name: Specific GCP service if applicable (e.g., 'Cloud Run', 'GKE', 'BigQuery', 'Vertex AI').
    """
    return {
        "status": "success",
        "service": service_name or "GCP General",
        "category": category,
        "summary": f"Retrieved relevant GCP details for: {query}",
        "details": "Documentation reference and best practices available."
    }


async def learning_assistant(
    topic: str,
    action: str = "explain",
    difficulty: str = "intermediate",
    user_answer: Optional[str] = None
) -> dict:
    """Facilitate interactive learning, quizzes, Socratic questions, and concept breakdowns.

    Args:
        topic: The subject or concept being learned (e.g., 'Kubernetes networking', 'Python decorators').
        action: The learning action ('explain', 'quiz_me', 'evaluate_answer', 'summarize_progress', 'step_by_step').
        difficulty: Difficulty level ('beginner', 'intermediate', 'advanced').
        user_answer: The user's answer if evaluating a quiz response.
    """
    return {
        "status": "success",
        "topic": topic,
        "action": action,
        "difficulty": difficulty,
        "result": f"Learning session ready for {topic} ({action})."
    }


async def display_visual(
    title: str,
    caption: str,
    visual_type: str = "diagram",
    image_keywords: Optional[str] = None,
    diagram_definition: Optional[str] = None,
    key_points: Optional[List[str]] = None
) -> dict:
    """Display pictorial information, diagrams, architecture charts, or illustrative images on the user's screen.

    Use this whenever the user asks to see an image, picture, diagram, chart, or visual representation of a concept or architecture.

    Args:
        title: Title of the visual display (e.g., 'GCP Cloud Run Architecture', 'Python Memory Model').
        caption: Short 1-2 sentence caption explaining what is shown.
        visual_type: The format of visual ('diagram', 'photo', 'infographic_card', 'chart').
        image_keywords: Search keywords for finding or generating the relevant image/illustration.
        diagram_definition: Optional Mermaid or ASCII diagram code if illustrating flow/architecture.
        key_points: Optional 2-4 key takeaways to highlight on the visual card.
    """
    image_url = ""
    if image_keywords:
        safe_query = urllib.parse.quote(image_keywords)
        image_url = f"https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop&q=80"

    return {
        "status": "displayed",
        "title": title,
        "caption": caption,
        "visual_type": visual_type,
        "image_url": image_url,
        "diagram": diagram_definition or "",
        "key_points": key_points or []
    }


async def send_resource_link(
    title: str,
    url: str,
    description: str = "",
    resource_type: str = "documentation"
) -> dict:
    """Send a clickable reference link, documentation URL, or whitepaper to the user's chat screen.

    Args:
        title: Display text for the link (e.g., 'Google Cloud Run Documentation', 'Python Official Tutorial').
        url: The web URL (e.g., 'https://cloud.google.com/run/docs').
        description: A short 1-line note explaining what the link contains.
        resource_type: Type of resource ('documentation', 'tutorial', 'whitepaper', 'code_repo').
    """
    return {
        "status": "link_sent",
        "title": title,
        "url": url,
        "description": description,
        "resource_type": resource_type
    }


def to_frontend_action(tool_name: str, tool_args: dict):
    """Translates tool executions into UI visual events."""
    if tool_name == "display_visual":
        return {"action": "render_visual", "data": tool_args}
    if tool_name == "send_resource_link":
        return {"action": "show_link_card", "data": tool_args}
    if tool_name == "gcp_assistant":
        return {"action": "show_gcp_card", "data": tool_args}
    if tool_name == "learning_assistant":
        return {"action": "show_learning_widget", "data": tool_args}
    return None
