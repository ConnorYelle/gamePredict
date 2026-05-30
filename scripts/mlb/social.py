#!/usr/bin/env python3
"""
Social post generation for Twitter and Instagram.
Improved architecture, parsing reliability, font caching,
and centralized team metadata.
"""

import abc
import math
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

from PIL import Image, ImageDraw, ImageFont  # type: ignore[import]

TEAM_DATA = {
    "los angeles dodgers": {
        "abbr": "LAD",
        "colors": ("#005a9c", "#ffffff")
    },
    "new york mets": {
        "abbr": "NYM",
        "colors": ("#002d72", "#ff5910")
    },
    "new york yankees": {
        "abbr": "NYY",
        "colors": ("#0c2340", "#ffffff")
    },
    "boston red sox": {
        "abbr": "BOS",
        "colors": ("#bd3039", "#0c2340")
    },
    "san francisco giants": {
        "abbr": "SF",
        "colors": ("#fd5a1e", "#000000")
    },
    "st louis cardinals": {
        "abbr": "STL",
        "colors": ("#c41e3a", "#000000")
    },
    "chicago cubs": {
        "abbr": "CHC",
        "colors": ("#0e3386", "#c8102e")
    },
    "chicago white sox": {
        "abbr": "CWS",
        "colors": ("#080806", "#c4ced4")
    },
    "tampa bay rays": {
        "abbr": "TB",
        "colors": ("#092c5c", "#8fbce6")
    },
    "oakland athletics": {
        "abbr": "OAK",
        "colors": ("#003831", "#f2d300")
    },
    "kansas city royals": {
        "abbr": "KC",
        "colors": ("#004687", "#ffffff")
    },
    "los angeles angels": {
        "abbr": "LAA",
        "colors": ("#ba0021", "#ffffff")
    },
    "texas rangers": {
        "abbr": "TEX",
        "colors": ("#003278", "#c0111f")
    },
    "washington nationals": {
        "abbr": "WSH",
        "colors": ("#ab0003", "#ffffff")
    },
    "atlanta braves": {
        "abbr": "ATL",
        "colors": ("#13274f", "#ce1141")
    },
    "seattle mariners": {
        "abbr": "SEA",
        "colors": ("#0c2c56", "#005c5c")
    },
    "san diego padres": {
        "abbr": "SD",
        "colors": ("#2f241d", "#f2a900")
    },
    "colorado rockies": {
        "abbr": "COL",
        "colors": ("#33006f", "#c4c4c4")
    },
    "miami marlins": {
        "abbr": "MIA",
        "colors": ("#00a3e0", "#f56416")
    },
    "cleveland guardians": {
        "abbr": "CLE",
        "colors": ("#0c2340", "#e8193d")
    },
    "detroit tigers": {
        "abbr": "DET",
        "colors": ("#0c2c56", "#f47321")
    },
    "pittsburgh pirates": {
        "abbr": "PIT",
        "colors": ("#fdcc0d", "#000000")
    },
    "toronto blue jays": {
        "abbr": "TOR",
        "colors": ("#134a8e", "#ffffff")
    },
    "philadelphia phillies": {
        "abbr": "PHI",
        "colors": ("#e81828", "#002d62")
    }
}


class TeamStyleService:
    @staticmethod
    def abbreviation(name: str) -> str:
        key = name.lower().strip()

        for team_name, data in TEAM_DATA.items():
            if team_name in key:
                return data["abbr"]

        words = [word for word in re.split(r"[\s\-&]+", name) if word]

        if len(words) >= 2:
            return (words[-2][0] + words[-1][0]).upper()

        if words:
            return words[0][:3].upper()

        return name[:3].upper()

    @staticmethod
    def colors(name: str) -> Tuple[str, str]:
        key = name.lower().strip()

        for team_name, data in TEAM_DATA.items():
            if team_name in key:
                return data["colors"]

        return ("#616161", "#f4f4f4")


class SocialPostGenerator(abc.ABC):
    def __init__(self, predictions: List[Dict[str, Any]]):
        self.predictions = predictions
        self.generated_at = datetime.now().strftime('%Y-%m-%d')

    def generate_post(self) -> str:
        header = self.build_header()
        body = self.build_body()
        footer = self.build_footer()

        return self.format_post(header, body, footer)

    @abc.abstractmethod
    def build_header(self) -> str:
        pass

    @abc.abstractmethod
    def build_body(self) -> str:
        pass

    def build_footer(self) -> str:
        return f"Generated on {self.generated_at} using gamePredict"

    def format_post(self, header: str, body: str, footer: str) -> str:
        parts = [header.strip(), body.strip()]

        if footer:
            parts.append(footer.strip())

        return "\n\n".join(parts)

    def top_games(self, limit: int = 3) -> List[Dict[str, Any]]:
        return sorted(
            self.predictions,
            key=lambda g: g['favorite_prob'],
            reverse=True
        )[:limit]

    def summary_line(self, game: Dict[str, Any]) -> str:
        return (
            f"{game['away']} @ {game['home']}: "
            f"{game['home_prob']:.1f}% / "
            f"{game['away_prob']:.1f}%"
        )


class TwitterPostGenerator(SocialPostGenerator):
    def build_header(self) -> str:
        return "MLB predictions for today"

    def build_body(self) -> str:
        if not self.predictions:
            return "No prediction data is available."

        lines = ["Top matchups:"]

        for game in self.top_games(3):
            lines.append(self.summary_line(game))

        favorite = max(
            self.predictions,
            key=lambda g: g['favorite_prob']
        )

        lines.append("")
        lines.append(
            f"Best pick: "
            f"{favorite['favorite']} "
            f"at {favorite['favorite_prob']:.1f}%"
        )

        lines.append("#MLB #Baseball #ProbableWinner")

        return "\n".join(lines)

    def build_footer(self) -> str:
        return "Data-driven MLB predictions from gamePredict"


class InstagramPostGenerator(SocialPostGenerator):
    def build_header(self) -> str:
        return "Today's MLB prediction recap"

    def build_body(self) -> str:
        if not self.predictions:
            return "No game predictions are available to share."

        lines = ["Matchups to watch:"]

        for game in self.top_games(5):
            tier = self.confidence_tier(game['favorite_prob'])

            lines.append(
                f"• {game['away']} @ {game['home']} "
                f"— {game['favorite']} "
                f"({game['favorite_prob']:.1f}%) [{tier}]"
            )

        lines.append("")
        lines.append(
            "Tap for more MLB analytics and daily predictions."
        )

        lines.append(
            "#MLBPrediction #BaseballAnalytics #GameDay"
        )

        return "\n".join(lines)

    def confidence_tier(self, prob: float) -> str:
        if prob >= 65:
            return "LOCK"

        if prob >= 58:
            return "LEAN"

        return "TOSS-UP"

    def build_footer(self) -> str:
        return "Built with the gamePredict pipeline"


class MatchupImageGenerator:
    def __init__(
        self,
        output_path: Path,
        width: int = 1400,
        height: int = 1080
    ):
        self.output_path = output_path
        self.width = width
        self.height = height

        self.bg_color = "#181818"
        self.panel_color = "#242424"
        self.accent_color = "#fb8500"
        self.text_color = "#f4f4f4"
        self.muted_text = "#b8b8b8"
        self.winner_color = "#2dd4bf"
        self.loser_color = "#d62828"
        self.divider_color = "#3b3b3b"

        self.title_font_name = "DejaVuSans-Bold.ttf"
        self.body_font_name = "DejaVuSans.ttf"

        self.font_cache = {}

    def load_font(self, size: int, bold: bool = False):
        key = (size, bold)

        if key in self.font_cache:
            return self.font_cache[key]

        candidates = (
            [self.title_font_name]
            if bold
            else [self.body_font_name, self.title_font_name]
        )

        for font_name in candidates:
            try:
                font = ImageFont.truetype(font_name, size)
                self.font_cache[key] = font
                return font
            except OSError:
                continue

        font = ImageFont.load_default()
        self.font_cache[key] = font

        return font

    def _draw_rounded_rect(
        self,
        draw,
        xy,
        radius,
        fill
    ):
        draw.rounded_rectangle(
            xy,
            radius=radius,
            fill=fill
        )

    def _text_size(self, draw, text, font):
        bbox = draw.textbbox((0, 0), text, font=font)

        return (
            bbox[2] - bbox[0],
            bbox[3] - bbox[1]
        )

    def _draw_logo_badge(
        self,
        draw,
        x,
        y,
        radius,
        team
    ):
        primary, secondary = TeamStyleService.colors(team)

        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=primary
        )

        inner_radius = int(radius * 0.68)

        draw.ellipse(
            [
                x - inner_radius,
                y - inner_radius,
                x + inner_radius,
                y + inner_radius
            ],
            fill=secondary
        )

        abbr = TeamStyleService.abbreviation(team)

        badge_font = self.load_font(24, bold=True)

        tw, th = self._text_size(draw, abbr, badge_font)

        draw.text(
            (x - tw / 2, y - th / 2),
            abbr,
            font=badge_font,
            fill=self.text_color
        )

    def _draw_team_block(
        self,
        draw,
        team,
        prob,
        label,
        x,
        y,
        width,
        height,
        is_winner
    ):
        self._draw_rounded_rect(
            draw,
            (x, y, x + width, y + height),
            22,
            self.panel_color
        )

        badge_x = x + 60
        badge_y = y + 60

        self._draw_logo_badge(
            draw,
            badge_x,
            badge_y,
            40,
            team
        )

        team_font = self.load_font(18, bold=True)

        draw.text(
            (x + 130, y + 30),
            team,
            font=team_font,
            fill=self.text_color
        )

        role_font = self.load_font(14)

        draw.text(
            (x + 130, y + 60),
            label.upper(),
            font=role_font,
            fill=self.muted_text
        )

        score_font = self.load_font(30, bold=True)

        score_text = f"{prob:.1f}%"

        draw.text(
            (x + 130, y + height - 58),
            score_text,
            font=score_font,
            fill=self.accent_color
        )

        status_text = (
            "WINNER"
            if is_winner
            else "UNDERDOG"
        )

        status_color = (
            self.winner_color
            if is_winner
            else self.loser_color
        )

        status_font = self.load_font(14, bold=True)

        status_w, _ = self._text_size(
            draw,
            status_text,
            status_font
        )

        draw.text(
            (x + width - status_w - 22, y + 20),
            status_text,
            font=status_font,
            fill=status_color
        )

        bar_x = x + 130
        bar_y = y + height - 24
        bar_width = width - 190

        draw.rectangle(
            [
                bar_x,
                bar_y,
                bar_x + bar_width,
                bar_y + 12
            ],
            fill=self.divider_color
        )

        fill_width = int(
            (prob / 100.0) * bar_width
        )

        draw.rectangle(
            [
                bar_x,
                bar_y,
                bar_x + fill_width,
                bar_y + 12
            ],
            fill=status_color
        )

    def generate_image(
        self,
        predictions: List[Dict[str, Any]]
    ):
        if not predictions:
            return

        sorted_matches = sorted(
            predictions,
            key=lambda g: g['swing'],
            reverse=True
        )

        match_count = len(sorted_matches)

        columns = min(3, match_count)
        rows = math.ceil(match_count / columns)

        card_height = 130
        card_gap = 20
        column_gap = 20

        top_padding = 150
        left_margin = 50
        right_margin = 50

        column_width = int(
            (
                self.width
                - left_margin
                - right_margin
                - (columns - 1) * column_gap
            ) / columns
        )

        total_height = (
            top_padding
            + rows * (card_height + card_gap)
            + 60
        )

        canvas_height = max(
            self.height,
            total_height
        )

        image = Image.new(
            "RGB",
            (self.width, canvas_height),
            self.bg_color
        )

        draw = ImageDraw.Draw(image)

        title_font = self.load_font(54, bold=True)
        subtitle_font = self.load_font(20)

        title_text = "MLB Matchup Preview"

        subtitle_text = (
            f"Updated "
            f"{datetime.now().strftime('%Y-%m-%d')}"
        )

        title_w, title_h = self._text_size(
            draw,
            title_text,
            title_font
        )

        draw.text(
            (
                (self.width - title_w) / 2,
                40
            ),
            title_text,
            font=title_font,
            fill=self.accent_color
        )

        sub_w, _ = self._text_size(
            draw,
            subtitle_text,
            subtitle_font
        )

        draw.text(
            (
                (self.width - sub_w) / 2,
                40 + title_h + 10
            ),
            subtitle_text,
            font=subtitle_font,
            fill=self.muted_text
        )

        for idx, game in enumerate(sorted_matches):
            row = idx // columns
            col = idx % columns

            x = left_margin + col * (
                column_width + column_gap
            )

            y = top_padding + row * (
                card_height + card_gap
            )

            self._draw_rounded_rect(
                draw,
                (
                    x,
                    y,
                    x + column_width,
                    y + card_height
                ),
                24,
                self.panel_color
            )

            split_width = int(
                (column_width - 48) / 2
            )

            self._draw_team_block(
                draw,
                game['away'],
                game['away_prob'],
                'away',
                x + 20,
                y + 12,
                split_width,
                card_height - 24,
                game['away_prob'] >= game['home_prob']
            )

            self._draw_team_block(
                draw,
                game['home'],
                game['home_prob'],
                'home',
                x + 28 + split_width,
                y + 12,
                split_width,
                card_height - 24,
                game['home_prob'] >= game['away_prob']
            )

            center_font = self.load_font(28, bold=True)

            draw.text(
                (
                    x + column_width / 2 - 16,
                    y + card_height / 2 - 18
                ),
                "VS",
                font=center_font,
                fill=self.accent_color
            )

        image.save(self.output_path)


class SocialPostManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def parse_predictions(
        self,
        raw_text: str
    ) -> List[Dict[str, Any]]:
        games = []

        lines = [
            line.strip()
            for line in raw_text.splitlines()
            if line.strip()
        ]

        game_pattern = re.compile(
            r'^(?P<away>.+) @ (?P<home>.+)$'
        )

        percent_pattern = re.compile(
            r'^(?P<team>.+?)\s+'
            r'(?P<percent>[0-9]+\.?[0-9]*)%$'
        )

        index = 0

        while index < len(lines):
            game_match = game_pattern.match(lines[index])

            if not game_match:
                index += 1
                continue

            away = game_match.group('away')
            home = game_match.group('home')

            index += 1

            percentages = []

            while (
                index < len(lines)
                and len(percentages) < 2
            ):
                line = lines[index]

                percent_match = percent_pattern.match(line)

                if percent_match:
                    percentages.append(percent_match)

                index += 1

            if len(percentages) != 2:
                continue

            away_prob = float(
                percentages[0].group('percent')
            )

            home_prob = float(
                percentages[1].group('percent')
            )

            favorite = (
                home
                if home_prob >= away_prob
                else away
            )

            favorite_prob = max(
                home_prob,
                away_prob
            )

            games.append({
                'away': away,
                'home': home,
                'away_prob': away_prob,
                'home_prob': home_prob,
                'favorite': favorite,
                'favorite_prob': favorite_prob,
                'swing': abs(
                    home_prob - away_prob
                )
            })

        return sorted(
            games,
            key=lambda g: g['favorite_prob'],
            reverse=True
        )

    def generate_social_posts(
        self,
        raw_text: str
    ):
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        predictions = self.parse_predictions(
            raw_text
        )

        twitter_post = (
            TwitterPostGenerator(
                predictions
            ).generate_post()
        )

        instagram_post = (
            InstagramPostGenerator(
                predictions
            ).generate_post()
        )

        self.save_text(
            'twitter_post.txt',
            twitter_post
        )

        self.save_text(
            'instagram_caption.txt',
            instagram_post
        )

        self.generate_social_image(
            predictions
        )

    def generate_social_image(
        self,
        predictions
    ):
        image_path = (
            self.output_dir
            / 'matchup_preview.png'
        )

        MatchupImageGenerator(
            image_path
        ).generate_image(predictions)

    def save_text(
        self,
        filename,
        content
    ):
        path = self.output_dir / filename

        with path.open(
            'w',
            encoding='utf-8'
        ) as f:
            f.write(content)