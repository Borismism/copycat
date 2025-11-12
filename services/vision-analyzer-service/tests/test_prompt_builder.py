"""Tests for prompt_builder.py"""

import pytest
from app.core.prompt_builder import PromptBuilder


class TestPromptBuilder:
    """Test PromptBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create prompt builder instance."""
        return PromptBuilder()

    def test_build_analysis_prompt_basic(self, builder, sample_video_metadata):
        """Test basic prompt generation."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        # Check that prompt contains key sections
        assert "COPYRIGHT INFRINGEMENT ANALYSIS" in prompt
        assert "LEGAL CONTEXT" in prompt
        assert "TARGET CHARACTERS" in prompt
        assert "ANALYSIS INSTRUCTIONS" in prompt
        assert "REQUIRED OUTPUT (JSON)" in prompt

    def test_prompt_includes_video_metadata(self, builder, sample_video_metadata):
        """Test that prompt includes video metadata."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert sample_video_metadata.video_id in prompt
        assert sample_video_metadata.title in prompt
        assert str(sample_video_metadata.duration_seconds) in prompt
        assert f"{sample_video_metadata.view_count:,}" in prompt
        assert sample_video_metadata.channel_title in prompt

    def test_prompt_includes_matched_characters(self, builder, sample_video_metadata):
        """Test that prompt includes matched characters."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        for character in sample_video_metadata.matched_characters:
            assert character in prompt

    def test_prompt_includes_all_jl_characters_when_none_matched(
        self, builder, sample_video_metadata
    ):
        """Test that all JL characters are included when none matched."""
        sample_video_metadata.matched_characters = []
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        for character in JUSTICE_LEAGUE_CHARACTERS:
            assert character in prompt

    def test_prompt_includes_copyright_law(self, builder, sample_video_metadata):
        """Test that prompt includes copyright law references."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "17 U.S.C." in prompt
        assert "Fair Use" in prompt
        assert "Copyright Infringement" in prompt

    def test_prompt_includes_ai_detection_instructions(
        self, builder, sample_video_metadata
    ):
        """Test AI-generated content detection instructions."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "Sora" in prompt or "AI" in prompt
        assert "Runway" in prompt
        assert "AI-generated" in prompt or "AI tools" in prompt

    def test_prompt_includes_json_schema(self, builder, sample_video_metadata):
        """Test that prompt includes JSON output schema."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        # Check for key JSON fields
        assert "contains_infringement" in prompt
        assert "confidence_score" in prompt
        assert "infringement_type" in prompt
        assert "ai_generated" in prompt
        assert "characters_detected" in prompt
        assert "copyright_assessment" in prompt

    def test_prompt_includes_fair_use_factors(self, builder, sample_video_metadata):
        """Test that prompt includes fair use analysis."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "fair_use" in prompt
        assert "purpose" in prompt
        assert "nature" in prompt
        assert "amount_used" in prompt
        assert "market_effect" in prompt

    def test_prompt_includes_examples(self, builder, sample_video_metadata):
        """Test that prompt includes examples of infringement."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "EXAMPLES" in prompt or "Example" in prompt

    def test_prompt_includes_evidence_requirements(
        self, builder, sample_video_metadata
    ):
        """Test that prompt requires evidence and timestamps."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "timestamp" in prompt.lower()
        assert "evidence" in prompt.lower()
        assert "reasoning" in prompt.lower()

    def test_prompt_length_reasonable(self, builder, sample_video_metadata):
        """Test that prompt length is reasonable."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        # Prompt should be substantial but not excessive
        assert 2000 < len(prompt) < 10000

    def test_prompt_with_multiple_characters(self, builder, sample_video_metadata):
        """Test prompt with multiple matched characters."""
        sample_video_metadata.matched_characters = [
            "Superman",
            "Batman",
            "Wonder Woman",
            "Flash",
        ]
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        for char in sample_video_metadata.matched_characters:
            assert char in prompt

    def test_prompt_format_character_list(self, builder):
        """Test character list formatting."""
        characters = ["Superman", "Batman", "Wonder Woman"]
        formatted = builder._format_character_list(characters)

        assert "- Superman" in formatted
        assert "- Batman" in formatted
        assert "- Wonder Woman" in formatted
        assert formatted.count("\n") == 2  # 3 items = 2 newlines

    def test_get_output_schema_is_valid_json(self, builder):
        """Test that output schema is valid JSON."""
        import json

        schema_str = builder._get_output_schema()
        schema = json.loads(schema_str)  # Should not raise

        # Check for key fields
        assert "contains_infringement" in schema
        assert "confidence_score" in schema
        assert "characters_detected" in schema

    def test_prompt_instructs_json_only_output(self, builder, sample_video_metadata):
        """Test that prompt instructs JSON-only output."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "ONLY" in prompt and "JSON" in prompt
        assert "Respond" in prompt

    def test_prompt_conservative_guidance(self, builder, sample_video_metadata):
        """Test that prompt includes conservative guidance."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "conservative" in prompt.lower() or "uncertain" in prompt.lower()

    def test_prompt_includes_legal_notes_field(self, builder, sample_video_metadata):
        """Test that prompt includes legal_notes field for human review."""
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        assert "legal_notes" in prompt
        assert "legal team" in prompt.lower()

    def test_prompt_with_high_views(self, builder, sample_video_metadata):
        """Test prompt formatting with high view counts."""
        sample_video_metadata.view_count = 1_250_000
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        # Should include formatted view count
        assert "1,250,000" in prompt or "1250000" in prompt

    def test_prompt_with_long_title(self, builder, sample_video_metadata):
        """Test prompt with very long video title."""
        sample_video_metadata.title = "A" * 200  # Very long title
        prompt = builder.build_analysis_prompt(sample_video_metadata)

        # Should still include title
        assert "A" * 50 in prompt  # At least part of it

    def test_prompt_consistency(self, builder, sample_video_metadata):
        """Test that same metadata produces same prompt."""
        prompt1 = builder.build_analysis_prompt(sample_video_metadata)
        prompt2 = builder.build_analysis_prompt(sample_video_metadata)

        assert prompt1 == prompt2

    def test_justice_league_characters_complete(self):
        """Test that all main JL characters are defined."""
        expected_characters = {
            "Superman",
            "Batman",
            "Wonder Woman",
            "The Flash",
            "Aquaman",
            "Cyborg",
            "Green Lantern",
        }

        assert set(JUSTICE_LEAGUE_CHARACTERS) == expected_characters
