#!/usr/bin/env python3
"""
Social post generation for Twitter and Instagram.
Uses a template method pattern to keep the content structure consistent.
"""

import abc
import mathimport mathimport re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from PIL import Image, ImageDraw, ImageFont

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
        return self.predictions[:limit]

    def summary_line(self, game: Dict[str, Any]) -> str:
        return f"{game['away']} @ {game['home']}: {game['home_prob']:.1f}% / {game['away_prob']:.1f}%"

class TwitterPostGenerator(SocialPostGenerator):
    def build_header(self) -> str:
        return "MLB predictions for today"

    def build_body(self) -> str:
        if not self.predictions:
            return "No prediction data is available."

        lines = ["Top matchups:"]
        for game in self.top_games(3):
            lines.append(self.summary_line(game))

        if self.predictions:
            favorite = self.predictions[0]
            lines.append("")
            lines.append(f"Best pick: {favorite['favorite']} at {favorite['favorite_prob']:.1f}%")

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
            lines.append(f"• {game['away']} @ {game['home']} — {game['home_prob']:.1f}% home")

        lines.append("")
        lines.append("Prediction insight:")

        if self.predictions:
            first_game = self.predictions[0]
            lines.append(
                f"{first_game['favorite']} is the favorite in the most confident game at {first_game['favorite_prob']:.1f}%"
            )

        lines.append("")
        lines.append("Tap for more MLB analytics and daily predictions.")
        lines.append("#MLBPrediction #BaseballAnalytics #GameDay")
        return "\n".join(lines)

    def build_footer(self) -> str:
        return "Built with the gamePredict pipeline"

class MatchupImageGenerator:
    def __init__(self, output_path: Path, width: int = 1400, height: int = 1080):
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
        self.logo_bg = "#303030"
        self.divider_color = "#3b3b3b"
        self.title_font_name = "DejaVuSans-Bold.ttf"
        self.body_font_name = "DejaVuSans.ttf"

    def load_font(self, size: int, bold: bool = False):
        candidates = [self.title_font_name] if bold else [self.body_font_name, self.title_font_name]
        for font_name in candidates:
            try:
                return ImageFont.truetype(font_name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def team_abbreviation(self, name: str) -> str:
        mapping = {
            "los angeles dodgers": "LAD",
            "new york mets": "NYM",
            "new york yankees": "NYY",
            "boston red sox": "BOS",
            "san francisco giants": "SF",
            "st louis cardinals": "STL",
            "chicago cubs": "CHC",
            "chicago white sox": "CWS",
            "tampa bay rays": "TB",
            "oakland athletics": "OAK",
            "kansas city royals": "KC",
            "los angeles angels": "LAA",
            "texas rangers": "TEX",
            "washington nationals": "WSH",
            "atlanta braves": "ATL",
            "seattle mariners": "SEA",
            "san diego padres": "SD",
            "colorado rockies": "COL",
            "miami marlins": "MIA",
            "cleveland guardians": "CLE",
            "detroit tigers": "DET",
            "chicago white sox": "CWS",
            "new york mets": "NYM"
        }
        key = name.lower().strip()
        for phrase, code in mapping.items():
            if phrase in key:
                return code

        words = [word for word in re.split(r"[\s\-&]+", name) if word]
        if len(words) >= 2:
            return (words[-2][0] + words[-1][0]).upper()
        if words:
            return words[0][:3].upper()
        return name[:3].upper()

    def team_logo_colors(self, name: str):
        palette = {
            "dodgers": ("#005a9c", "#ffffff"),
            "mets": ("#002d72", "#ff5910"),
            "yankees": ("#0c2340", "#ffffff"),
            "red sox": ("#bd3039", "#0c2340"),
            "giants": ("#fd5a1e", "#000000"),
            "cardinals": ("#c41e3a", "#000000"),
            "cubs": ("#0e3386", "#c8102e"),
            "white sox": ("#080806", "#c4ced4"),
            "rays": ("#092c5c", "#8fbce6"),
            "athletics": ("#003831", "#f2d300"),
            "royals": ("#004687", "#ffffff"),
            "angels": ("#ba0021", "#ffffff"),
            "rangers": ("#003278", "#c0111f"),
            "nationals": ("#ab0003", "#ffffff"),
            "braves": ("#13274f", "#ce1141"),
            "mariners": ("#0c2c56", "#005c5c"),
            "padres": ("#2f241d", "#f2a900"),
            "rockies": ("#33006f", "#c4c4c4"),
            "marlins": ("#00a3e0", "#f56416"),
            "guardians": ("#0c2340", "#e8193d"),
            "tigers": ("#0c2c56", "#f47321"),
            "pirates": ("#fdcc0d", "#000000"),
            "blue jays": ("#134a8e", "#ffffff"),
            "phillies": ("#e81828", "#002d62"),
            "nationals": ("#ab0003", "#ffffff")
        }
        key = name.lower()
        for phrase, colors in palette.items():
            if phrase in key:
                return colors
        return ("#616161", "#f4f4f4")
    
    def safe_rect(draw, x0, y0, x1, y1, **kwargs):
        if x1 <= x0 or y1 <= y0:
            return
        draw.safe_rect([x0, y0, x1, y1], **kwargs)

    def _draw_rounded_rect(self, draw: ImageDraw.ImageDraw, xy, radius, fill):
        x0, y0, x1, y1 = xy
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)

    def _text_size(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _draw_logo_badge(self, draw: ImageDraw.ImageDraw, x: int, y: int, radius: int, team: str):
        primary, secondary = self.team_logo_colors(team)
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=primary)
        inner_radius = int(radius * 0.68)
        draw.ellipse([x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius], fill=secondary)

        abbr = self.team_abbreviation(team)
        badge_font = self.load_font(24, bold=True)
        tw, th = self._text_size(draw, abbr, badge_font)
        draw.text((x - tw / 2, y - th / 2), abbr, font=badge_font, fill=primary)

    def _draw_team_block(self, draw: ImageDraw.ImageDraw, team: str, prob: float, label: str, x: int, y: int, width: int, height: int, is_winner: bool):
        draw.rectangle([x, y, x + width, y + height], fill=self.panel_color)
        self._draw_rounded_rect(draw, (x, y, x + width, y + height), 22, self.panel_color)

        badge_x = x + 60
        badge_y = y + 60
        badge_radius = min(40, int(height * 0.28))
        self._draw_logo_badge(draw, badge_x, badge_y, badge_radius, team)

        team_font = self.load_font(18, bold=True)
        team_name_w, team_name_h = self._text_size(draw, team, team_font)
        draw.text((x + 130, y + 30), team, font=team_font, fill=self.text_color)

        role_font = self.load_font(14)
        role_label = label.upper()
        draw.text((x + 130, y + 30 + team_name_h + 6), role_label, font=role_font, fill=self.muted_text)

        score_font = self.load_font(30, bold=True)
        score_text = f"{prob:.1f}%"
        score_w, score_h = self._text_size(draw, score_text, score_font)
        draw.text((x + 130, y + height - score_h - 20), score_text, font=score_font, fill=self.accent_color)

        status_text = "WINNER" if is_winner else "UNDERDOG"
        status_color = self.winner_color if is_winner else self.loser_color
        status_font = self.load_font(14, bold=True)
        status_w, status_h = self._text_size(draw, status_text, status_font)
        draw.text((x + width - status_w - 22, y + 20), status_text, font=status_font, fill=status_color)

        bar_x = x + 130
        bar_y = y + height - 36
        bar_width = width - 190
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + 12], fill=self.divider_color)
        fill_width = int((prob / 100.0) * bar_width)
        draw.rectangle([bar_x, bar_y, bar_x + fill_width, bar_y + 12], fill=status_color)

        team_abbr_font = self.load_font(14, bold=True)
        abbr = self.team_abbreviation(team)
        abbr_w, abbr_h = self._text_size(draw, abbr, team_abbr_font)
        draw.text((x + 60 - abbr_w / 2, y + 100), abbr, font=team_abbr_font, fill=self.text_color)

    def generate_image(self, predictions: List[Dict[str, Any]]) -> None:
        if not predictions:
            return

        sorted_matches = sorted(predictions, key=lambda g: abs(g['home_prob'] - g['away_prob']), reverse=True)
        match_count = len(sorted_matches)
        columns = min(4, max(1, math.ceil(match_count / 4)))
        rows = math.ceil(match_count / columns)
        card_height = 130
        card_gap = 20
        top_padding = 150
        left_margin = 50
        right_margin = 50
        column_gap = 20
        column_width = int((self.width - left_margin - right_margin - (columns - 1) * column_gap) / columns)
        column_width = max(320, column_width)
        total_height = top_padding + rows * (card_height + card_gap) + 60
        canvas_height = max(self.height, total_height)

        image = Image.new("RGB", (self.width, canvas_height), self.bg_color)
        draw = ImageDraw.Draw(image)

        title_font = self.load_font(54, bold=True)
        subtitle_font = self.load_font(20)
        divider_font = self.load_font(14)

        title_text = "MLB Matchup Preview"
        sub_text = f"Sorted by biggest swing · Updated {datetime.now().strftime('%Y-%m-%d')}"
        title_w, title_h = self._text_size(draw, title_text, title_font)
        draw.text(((self.width - title_w) / 2, 40), title_text, font=title_font, fill=self.accent_color)

        sub_w, sub_h = self._text_size(draw, sub_text, subtitle_font)
        draw.text(((self.width - sub_w) / 2, 40 + title_h + 10), sub_text, font=subtitle_font, fill=self.muted_text)

        for idx, game in enumerate(sorted_matches):
            col = idx // rows
            row = idx % rows
            x = left_margin + col * (column_width + column_gap)
            y = top_padding + row * (card_height + card_gap)
            self._draw_rounded_rect(draw, (x, y, x + column_width, y + card_height), radius=24, fill=self.panel_color)

            split_width = max(90, (column_width - 48) // 2)
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

            center_text = "VS"
            center_font = self.load_font(28, bold=True)
            center_w, center_h = self._text_size(draw, center_text, center_font)
            center_x = x + (column_width / 2) - (center_w / 2)
            center_y = y + (card_height / 2) - (center_h / 2)
            draw.text((center_x, center_y), center_text, font=center_font, fill=self.accent_color)

            swing_text = f"Swing: {abs(game['home_prob'] - game['away_prob']):.1f}%"
            swing_w, swing_h = self._text_size(draw, swing_text, divider_font)
            draw.text((x + column_width - swing_w - 18, y + 18), swing_text, font=divider_font, fill=self.muted_text)

        image.save(self.output_path)

class SocialPostManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def parse_predictions(self, raw_text: str) -> List[Dict[str, Any]]:
        games = []
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        game_pattern = re.compile(r'^(?P<away>.+) @ (?P<home>.+)$')
        percent_pattern = re.compile(r'^(?P<team>.+?)\s+(?P<percent>[0-9]+\.?[0-9]*)%$')

        index = 0
        while index < len(lines):
            match = game_pattern.match(lines[index])
            if not match:
                index += 1
                continue

            away = match.group('away')
            home = match.group('home')
            percent_lines = []
            index += 1

            while index < len(lines) and len(percent_lines) < 2:
                if lines[index].startswith("-") or lines[index].startswith("Favorite:"):
                    index += 1
                    continue
                if percent_pattern.match(lines[index]):
                    percent_lines.append(lines[index])
                index += 1

            if len(percent_lines) == 2:
                away_match = percent_pattern.match(percent_lines[0])
                home_match = percent_pattern.match(percent_lines[1])
                if away_match and home_match:
                    away_prob = float(away_match.group('percent'))
                    home_prob = float(home_match.group('percent'))
                    favorite = home if home_prob >= away_prob else away
                    favorite_prob = max(home_prob, away_prob)
                    games.append({
                        'away': away,
                        'home': home,
                        'away_prob': away_prob,
                        'home_prob': home_prob,
                        'favorite': favorite,
                        'favorite_prob': favorite_prob,
                        'swing': abs(home_prob - away_prob)
                    })
            continue

        return games

    def generate_social_posts(self, raw_text: str) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        predictions = self.parse_predictions(raw_text)

        twitter_post = TwitterPostGenerator(predictions).generate_post()
        instagram_post = InstagramPostGenerator(predictions).generate_post()

        self.save_text('twitter_post.txt', twitter_post)
        self.save_text('instagram_caption.txt', instagram_post)
        self.generate_social_image(predictions)

    def generate_social_image(self, predictions: List[Dict[str, Any]]) -> None:
        image_path = self.output_dir / 'matchup_preview.png'
        MatchupImageGenerator(image_path).generate_image(predictions)

    def save_text(self, filename: str, content: str) -> None:
        path = self.output_dir / filename
        with path.open('w', encoding='utf-8') as f:
            f.write(content)
