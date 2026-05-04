"""
Slug generator for Layer 5.
Produces a URL-safe, human-readable slug for each grant program.
"""
import re


def generate_slug(org_name: str, program_name: str, ein: str) -> str:
    """
    Generate a unique slug: <org-slug>-<program-slug>-<ein-suffix>
    Example: "akindale-foundation-community-arts-grant-237421854"
    """
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        text = re.sub(r"^-+|-+$", "", text)
        return text[:60]

    org_slug = slugify(org_name)
    prog_slug = slugify(program_name)
    ein_suffix = ein.replace("-", "")[-6:]  # last 6 digits of EIN as uniquifier

    raw = f"{org_slug}-{prog_slug}-{ein_suffix}"
    return raw[:120]
