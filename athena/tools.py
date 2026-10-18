import contextvars

visual_callback_var = contextvars.ContextVar('visual_callback', default=None)

"""Tools available to Athena."""


async def gcp_assistant(
    query: str, category: str = "general", service_name: str | None = None
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
        "details": "Documentation reference and best practices available.",
    }


async def learning_assistant(
    topic: str,
    action: str = "explain",
    difficulty: str = "intermediate",
    user_answer: str | None = None,
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
        "result": f"Learning session ready for {topic} ({action}).",
    }


async def display_visual(
    title: str,
    caption: str,
    visual_type: str = "image",
    image_prompt: str | None = None,
    diagram_definition: str | None = None,
    key_points: list[str] | None = None,
) -> dict:
    """Generate and display a picture, illustration, diagram, chart or infographic on the user's screen.

    Use this whenever the user asks to see, draw, show, generate or visualize something.
    The image is created by a separate image model and appears on screen in a few seconds.

    Args:
        title: Short title of the visual (e.g., 'Cloud Run Architecture', 'A Cyberpunk Owl').
        caption: 1-2 sentence caption explaining what is shown.
        visual_type: 'image' (picture/photo/art), 'illustration', 'diagram' (flow/architecture), 'chart', or 'infographic'.
        image_prompt: A rich, detailed visual description (subject, style, colors, composition, lighting). Required for image/illustration/infographic/chart.
        diagram_definition: Optional Mermaid code (flowchart/sequence) for simple flow or architecture diagrams.
        key_points: Optional 2-4 short takeaways to show under the visual.
    """
    from .visuals import generate_visual

    result = await generate_visual(
        title=title,
        caption=caption,
        visual_type=visual_type,
        image_prompt=image_prompt or f"{title}. {caption}",
        diagram_definition=diagram_definition,
        key_points=key_points or [],
    )
    cb = visual_callback_var.get()
    if cb:
        import asyncio
        asyncio.create_task(cb(result))
    return result


async def send_resource_link(
    title: str, url: str, description: str = "", resource_type: str = "documentation"
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
        "resource_type": resource_type,
    }


def to_frontend_action(tool_name: str, tool_args: dict):
    """Translates tool executions into UI visual events."""
    # display_visual is NOT forwarded at call time: the server sends a "visual_pending"
    # placeholder first and the finished image when the tool response arrives.
    if tool_name == "send_resource_link":
        return {"action": "show_link_card", "data": tool_args}
    if tool_name == "gcp_assistant":
        return {"action": "show_gcp_card", "data": tool_args}
    if tool_name == "learning_assistant":
        return {"action": "show_learning_widget", "data": tool_args}
    # Browser tools are handled upon function_response in server.py to show actual results
    return None
