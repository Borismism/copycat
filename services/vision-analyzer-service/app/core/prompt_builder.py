"""Build copyright-aware prompts for Gemini video analysis.

This module creates legally-informed prompts that:
- Understand copyright law and fair use doctrine
- Target configured intellectual property characters (from IPConfig)
- Detect AI-generated content
- Provide structured JSON output
- Include evidence and reasoning

Configuration is loaded dynamically from Firestore via config_loader.
"""

import json
import logging
from typing import Optional

from ..models import VideoMetadata
from .config_loader import IPConfig

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Build prompts for copyright infringement analysis."""

    def build_analysis_prompt(
        self, video_metadata: VideoMetadata, configs: list[IPConfig]
    ) -> str:
        """
        Create multi-IP copyright analysis prompt.

        Args:
            video_metadata: Video information from discovery/risk services
            configs: List of IP configurations this video matches

        Returns:
            Multi-IP prompt string
        """
        return self.build_multi_ip_prompt(video_metadata, configs)

    def build_multi_ip_prompt(
        self, video_metadata: VideoMetadata, configs: list[IPConfig]
    ) -> str:
        """
        Create prompt for videos that match MULTIPLE IPs.

        Args:
            video_metadata: Video information
            configs: List of IP configurations (2+)

        Returns:
            Prompt for multi-IP analysis
        """
        all_configs_text = []
        for config in configs:
            char_list = ", ".join(config.characters[:10])  # First 10 chars
            if len(config.characters) > 10:
                char_list += f", ... ({len(config.characters)} total)"

            all_configs_text.append(f"""
### {config.name} ({config.owner})
**Characters**: {char_list}
**Visual markers**: {', '.join(config.visual_keywords[:5])}
**AI patterns**: {', '.join(config.ai_tool_patterns[:5])}
""")

        prompt = f"""# MULTI-IP COPYRIGHT INFRINGEMENT ANALYSIS

You are a copyright analysis expert evaluating this YouTube video for potential infringement of MULTIPLE intellectual properties.

## VIDEO INFORMATION

- **Video ID**: {video_metadata.video_id}
- **Title**: {video_metadata.title}
- **Channel**: {video_metadata.channel_title}
- **Duration**: {video_metadata.duration_seconds} seconds
- **View Count**: {video_metadata.view_count:,}

## INTELLECTUAL PROPERTIES TO CHECK

This video may contain characters from multiple IPs. Analyze EACH IP separately:

{''.join(all_configs_text)}

## LEGAL FRAMEWORK

### Fair Use Doctrine (17 U.S.C. § 107)

**IMPORTANT**: Many uses are LEGITIMATE and NOT infringement:
- **Personal Use**: Costumes at parties, cosplay, home videos
- **Licensed Products**: Toys, merchandise unboxing/reviews
- **Commentary/Criticism**: Reviews, analysis with discussion
- **Educational**: Tutorials, teaching content
- **News/Documentary**: Reporting, industry coverage

Fair use applies when:
1. **Purpose**: Commentary, criticism, education, parody, or transformative
2. **Nature**: Factual use or adds new expression
3. **Amount**: Minimal necessary portion
4. **Market Effect**: Doesn't substitute or harm original market

### AI-Generated Content

AI tools (Sora, Runway, Kling, etc.) do NOT grant copyright permissions:
- AI-generated character content = unauthorized derivative work
- Full AI movies/episodes = high infringement risk
- Length matters: 30min movie >> 10s clip

## ANALYSIS INSTRUCTIONS

For EACH IP that appears in the video:
1. **Identify characters** from that IP
2. **Detect AI generation** (tools, artifacts, watermarks)
3. **Assess infringement** considering fair use
4. **Evaluate fair use factors** for that specific IP
5. **Provide detailed reasoning** with timestamps

## REQUIRED OUTPUT FORMAT

Respond with ONLY valid JSON matching this schema:

{{
  "ip_results": [
    {{
      "ip_id": "string - IP config ID",
      "ip_name": "string - IP name",
      "contains_infringement": "boolean - infringement for this IP?",
      "characters_detected": [
        {{
          "name": "string - character name",
          "screen_time_seconds": "number",
          "prominence": "string - primary|secondary|background",
          "timestamps": ["array of strings - MM:SS format"],
          "description": "string - visual details (2-3 sentences)"
        }}
      ],
      "is_ai_generated": "boolean - AI-generated content?",
      "ai_tools_detected": ["array of strings - Sora, Runway, etc."],
      "fair_use_applies": "boolean - does fair use apply for this IP?",
      "fair_use_reasoning": "string - explain why fair use does/doesn't apply (2-3 sentences)",
      "content_type": "string - full_movie|trailer|clips|review|cosplay|toys|news|tutorial|gameplay|other",
      "infringement_likelihood": "number 0-100",
      "reasoning": "string - detailed legal reasoning with timestamps (4-6 sentences)",
      "recommended_action": "string - immediate_takedown|monitor|safe_harbor|ignore"
    }}
  ],
  "overall_recommendation": "string - immediate_takedown|monitor|safe_harbor|ignore",
  "overall_notes": "string - overall assessment considering all IPs (2-3 sentences)"
}}

Now analyze the provided video for ALL listed IPs and respond with ONLY the JSON output.
"""
        return prompt

