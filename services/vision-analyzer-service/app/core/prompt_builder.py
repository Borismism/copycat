"""Build copyright-aware prompts for Gemini video analysis.

This module creates legally-informed prompts that:
- Understand copyright law and fair use doctrine
- Target configured intellectual property characters (from IPConfig)
- Detect AI-generated content
- Provide structured JSON output
- Include evidence and reasoning

Configuration is loaded dynamically from Firestore via config_loader.
"""

import logging

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

## INFRINGEMENT EXAMPLES & GUIDELINES

To ensure consistent assessment, here are concrete examples for each recommended action:

### 🚨 IMMEDIATE TAKEDOWN (immediate_takedown)
Clear infringement with high commercial impact or extensive unauthorized use:

**Examples:**
- **Full episodes/movies**: Complete copyrighted episodes or films uploaded without permission (e.g., "Justice League Full Movie 2023")
- **AI-generated narratives**: AI-created videos featuring copyrighted characters in new storylines/adventures, especially if monetized or lengthy (>5min)
- **Unauthorized merchandise**: Videos promoting/selling unlicensed products featuring copyrighted characters
- **Commercial deepfakes**: AI-generated content using IP for advertising, sponsorships, or commercial purposes
- **Content farms**: Channels systematically uploading copyrighted content for ad revenue

**Key indicators:** High view count (>100k), monetization enabled, lengthy content (>10min), commercial context, no transformative purpose

### ⚠️ TOLERATED (tolerated)
Technically infringing but culturally accepted and rarely prosecuted. **IMPORTANT: Still monitor these channels - creators may escalate to more serious infringement or commercial use.**

**Examples:**
- **Fan cosplay videos**: People in homemade costumes acting as characters (non-commercial, low production value)
- **Fan animations/art**: Amateur fan-created content celebrating the IP (low view count, clearly non-professional)
- **Tribute videos**: Fan compilations or homages showing appreciation for characters/franchises
- **Low-budget fan films**: Short amateur narratives featuring IP characters (clearly non-commercial, artistic expression)

**Key indicators:** Non-commercial intent, low/moderate views (<50k), amateur production quality, fan community context, no monetization, transformative fan expression

**Why monitor?** Fan creators may:
- Add monetization later
- Transition to commercial content
- Gain large audiences requiring action
- Cross into less-tolerated territory (e.g., merchandise sales)

### ✅ SAFE HARBOR (safe_harbor)
Protected by fair use doctrine - legitimate legal uses:

**Examples:**
- **Reviews/commentary**: Video essays analyzing characters, plotlines, or franchise decisions with clips for discussion
- **Educational content**: Film school tutorials, animation breakdowns, character design analysis
- **Parody/satire**: Humorous reinterpretations that comment on or criticize the original IP
- **News/journalism**: Entertainment news covering franchise announcements, actor interviews, industry trends
- **Unboxing licensed products**: Reviews of official merchandise, toys, games (commercial products viewer purchased)

**Key indicators:** Transformative purpose, commentary/criticism, educational value, minimal use necessary for purpose, doesn't substitute for original

### ⏸️ MONITOR (monitor)
Unclear or borderline cases requiring human review:

**Examples:**
- **Ambiguous context**: Can't determine if content is licensed, authorized, or falls under fair use
- **Partial transformation**: Some transformative elements but significant unauthorized use
- **Growing channels**: Tolerated content gaining rapid traction (may need intervention)
- **Mixed use cases**: Combination of fair use and infringing elements

### ✓ IGNORE (ignore)
No infringement detected:

**Examples:**
- **Original content**: No copyrighted characters, designs, or IP elements present
- **Licensed/official content**: Content from official channels or clearly licensed partners
- **Generic concepts**: Superhero content without specific copyrighted characters (e.g., generic "flying hero" without Superman's costume/logo)
- **Name-only mentions**: Video titles mentioning characters but content doesn't actually use the IP

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
      "recommended_action": "string - immediate_takedown|tolerated|monitor|safe_harbor|ignore"
    }}
  ],
  "overall_recommendation": "string - immediate_takedown|tolerated|monitor|safe_harbor|ignore",
  "overall_notes": "string - overall assessment considering all IPs (2-3 sentences)"
}}

Now analyze the provided video for ALL listed IPs and respond with ONLY the JSON output.
"""
        return prompt

