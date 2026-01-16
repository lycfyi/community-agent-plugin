"""Bot persona configuration and management.

Provides persona presets and custom persona builder for community agents.
Personas define how the bot presents itself (name, role, personality, tasks).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotPersona:
    """Complete bot persona configuration."""

    name: str                           # Bot's display name (e.g., "Luna", "Alex")
    role: str                           # Job title/role (e.g., "Community Manager")
    personality: str                    # Personality description
    tasks: list[str] = field(default_factory=list)  # What the bot does
    communication_style: str = ""       # How the bot communicates
    background: str = ""                # Optional backstory/context
    preset: str = "custom"              # Which preset this is based on

    def to_dict(self) -> dict:
        """Convert to dictionary for config storage."""
        return {
            "preset": self.preset,
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "tasks": self.tasks,
            "communication_style": self.communication_style,
            "background": self.background,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BotPersona":
        """Create from dictionary."""
        return cls(
            preset=data.get("preset", "custom"),
            name=data.get("name", ""),
            role=data.get("role", ""),
            personality=data.get("personality", ""),
            tasks=data.get("tasks", []),
            communication_style=data.get("communication_style", ""),
            background=data.get("background", ""),
        )

    def to_prompt(self) -> str:
        """Generate LLM prompt segment from persona."""
        lines = [
            f"You are {self.name}, a {self.role}.",
            f"Personality: {self.personality}",
            "",
        ]

        if self.tasks:
            lines.append("Your responsibilities:")
            for task in self.tasks:
                lines.append(f"- {task}")
            lines.append("")

        if self.communication_style:
            lines.append(f"Communication style: {self.communication_style}")
            lines.append("")

        if self.background:
            lines.append(f"Background: {self.background}")

        return "\n".join(lines).strip()


# Preset persona templates
PERSONA_PRESETS: dict[str, BotPersona] = {
    "community_manager": BotPersona(
        preset="community_manager",
        name="Alex",
        role="Community Manager",
        personality="Professional, organized, and helpful. Keeps discussions on track.",
        tasks=[
            "Welcome new members",
            "Answer community questions",
            "Summarize discussions",
            "Highlight important announcements",
        ],
        communication_style="Clear and professional, uses bullet points for clarity",
        background="Experienced community manager who knows the ins and outs",
    ),
    "friendly_helper": BotPersona(
        preset="friendly_helper",
        name="Luna",
        role="Community Helper",
        personality="Warm, encouraging, and patient. Makes everyone feel welcome.",
        tasks=[
            "Help newcomers get started",
            "Answer questions with patience",
            "Celebrate member achievements",
            "Create a welcoming atmosphere",
        ],
        communication_style="Friendly and conversational, uses occasional emoji",
        background="A supportive friend who's always happy to help",
    ),
    "tech_expert": BotPersona(
        preset="tech_expert",
        name="Dev",
        role="Technical Support",
        personality="Knowledgeable, precise, and thorough. Loves diving into details.",
        tasks=[
            "Answer technical questions",
            "Provide code examples",
            "Debug issues",
            "Share best practices",
        ],
        communication_style="Technical but accessible, includes code snippets",
        background="Senior developer who enjoys teaching",
    ),
}


# Predefined options for custom persona builder
PERSONA_OPTIONS = {
    "names": ["Sage", "Atlas", "Nova", "Echo", "Aria", "Scout"],
    "roles": [
        "Community Manager",
        "Community Moderator",
        "Support Agent",
        "Engagement Specialist",
        "Content Curator",
        "Event Coordinator",
        "Onboarding Guide",
    ],
    "personalities": [
        "Professional and organized",
        "Warm and encouraging",
        "Energetic and enthusiastic",
        "Calm and patient",
        "Witty and playful",
        "Knowledgeable and thorough",
    ],
    "tasks": [
        "Welcome new members",
        "Answer community questions",
        "Moderate discussions",
        "Summarize conversations",
        "Share announcements",
        "Collect feedback",
        "Facilitate introductions",
        "Track engagement metrics",
        "Highlight active contributors",
    ],
    "communication_styles": [
        "Formal and professional",
        "Friendly with occasional emoji",
        "Casual and conversational",
        "Enthusiastic with lots of emoji",
        "Brief and to-the-point",
    ],
    "backgrounds": [
        "Experienced community veteran",
        "Passionate about helping others",
        "Expert in community building",
    ],
}


def get_preset(preset_name: str) -> Optional[BotPersona]:
    """Get a persona preset by name.

    Args:
        preset_name: Name of the preset (community_manager, friendly_helper, tech_expert)

    Returns:
        BotPersona instance or None if not found
    """
    return PERSONA_PRESETS.get(preset_name)


def get_default_persona() -> BotPersona:
    """Get the default persona (community_manager)."""
    return PERSONA_PRESETS["community_manager"]


def list_presets() -> list[tuple[str, BotPersona]]:
    """List all available presets.

    Returns:
        List of (preset_id, BotPersona) tuples
    """
    return list(PERSONA_PRESETS.items())


def print_preset_options() -> None:
    """Print available persona presets in a formatted way."""
    print("Choose a Bot Persona:")
    print("-" * 50)

    for i, (preset_id, persona) in enumerate(PERSONA_PRESETS.items(), 1):
        print(f"  {i}. {persona.name} - {persona.role}")
        # Show first line of personality
        personality_preview = persona.personality.split(".")[0]
        print(f"     {personality_preview}.")
        print()

    print(f"  {len(PERSONA_PRESETS) + 1}. Custom - Create your own persona")
    print()


def prompt_with_options_single(
    prompt: str,
    options: list[str],
    allow_other: bool = True,
) -> str:
    """Display options and get single user selection.

    Args:
        prompt: Question to display
        options: List of options
        allow_other: Whether to allow custom input

    Returns:
        Selected value
    """
    print(f"\n{prompt}")

    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")

    if allow_other:
        print(f"  {len(options) + 1}. Other (type your own)")

    print(f"\nEnter choice [1-{len(options) + (1 if allow_other else 0)}]: ", end="")

    try:
        user_input = input().strip()
    except EOFError:
        # Non-interactive, return first option
        return options[0]

    try:
        idx = int(user_input) - 1
        if 0 <= idx < len(options):
            return options[idx]
        elif allow_other and idx == len(options):
            print("Enter custom value: ", end="")
            return input().strip() or options[0]
    except ValueError:
        pass
    return options[0]


def prompt_with_options_multiple(
    prompt: str,
    options: list[str],
    allow_other: bool = True,
) -> list[str]:
    """Display options and get multiple user selections.

    Args:
        prompt: Question to display
        options: List of options
        allow_other: Whether to allow custom input

    Returns:
        List of selected values
    """
    print(f"\n{prompt}")

    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")

    if allow_other:
        print(f"  {len(options) + 1}. Other (type your own)")

    print("\nEnter choices (comma-separated): ", end="")

    try:
        user_input = input().strip()
    except EOFError:
        # Non-interactive, return first option
        return options[:1]

    # Parse comma-separated choices
    results = []
    for part in user_input.split(","):
        part = part.strip()
        try:
            idx = int(part) - 1
            if 0 <= idx < len(options):
                results.append(options[idx])
            elif allow_other and idx == len(options):
                print("Enter custom value: ", end="")
                custom = input().strip()
                if custom:
                    results.append(custom)
        except ValueError:
            # Treat as custom input
            if part:
                results.append(part)
    return results if results else options[:1]


def build_custom_persona() -> BotPersona:
    """Interactive builder for custom persona.

    Returns:
        BotPersona with user-selected values
    """
    print("\nCustom Persona Setup")
    print("-" * 50)

    name = prompt_with_options_single(
        "What should the bot be called?",
        PERSONA_OPTIONS["names"],
        allow_other=True,
    )
    print(f"> Name: {name}")

    role = prompt_with_options_single(
        "What's the bot's role?",
        PERSONA_OPTIONS["roles"],
        allow_other=True,
    )
    print(f"> Role: {role}")

    personality = prompt_with_options_single(
        "What's the bot's personality?",
        PERSONA_OPTIONS["personalities"],
        allow_other=True,
    )
    print(f"> Personality: {personality}")

    tasks = prompt_with_options_multiple(
        "What are the bot's main tasks? (select multiple, comma-separated)",
        PERSONA_OPTIONS["tasks"],
        allow_other=True,
    )
    print(f"> Tasks: {', '.join(tasks)}")

    communication_style = prompt_with_options_single(
        "How should the bot communicate?",
        PERSONA_OPTIONS["communication_styles"],
        allow_other=True,
    )
    print(f"> Style: {communication_style}")

    background_options = PERSONA_OPTIONS["backgrounds"] + ["Skip (no background)"]
    background = prompt_with_options_single(
        "(Optional) Background context for the bot?",
        background_options,
        allow_other=True,
    )
    if background == "Skip (no background)":
        background = ""
    else:
        print(f"> Background: {background}")

    print(f"\nPersona created: {name} ({role})")

    return BotPersona(
        preset="custom",
        name=name,
        role=role,
        personality=personality,
        tasks=tasks,
        communication_style=communication_style,
        background=background,
    )


def select_persona_interactive() -> BotPersona:
    """Interactive persona selection.

    Shows preset options and allows custom creation.

    Returns:
        Selected or created BotPersona
    """
    print_preset_options()

    print(f"Enter choice [1-{len(PERSONA_PRESETS) + 1}]: ", end="")

    try:
        user_input = input().strip()
    except EOFError:
        # Non-interactive, return default
        return get_default_persona()

    try:
        choice = int(user_input)
        preset_list = list(PERSONA_PRESETS.values())

        if 1 <= choice <= len(preset_list):
            selected = preset_list[choice - 1]
            print(f"\nSelected: {selected.name} ({selected.role})")
            print(f"  Role: {selected.role}")
            print(f"  Personality: {selected.personality.split('.')[0]}.")
            print(f"  Style: {selected.communication_style}")
            return selected
        elif choice == len(preset_list) + 1:
            return build_custom_persona()
    except ValueError:
        pass

    # Default to community_manager
    return get_default_persona()


def select_persona_quickstart() -> BotPersona:
    """Select persona for quickstart mode (non-interactive).

    Returns:
        Default community_manager persona
    """
    return get_default_persona()
