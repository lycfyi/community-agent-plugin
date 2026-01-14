"""Progress tracking utility for analytics operations.

Provides progress indication with percentage and ETA for large dataset analysis.
"""

import sys
import time
from typing import Optional


class ProgressTracker:
    """Track and display progress for long-running operations.

    Supports percentage display and ETA calculation.
    """

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        show_eta: bool = True,
        output=sys.stdout
    ):
        """Initialize progress tracker.

        Args:
            total: Total number of items to process.
            description: Description of the operation.
            show_eta: Whether to show ETA.
            output: Output stream (default: stdout).
        """
        self.total = total
        self.description = description
        self.show_eta = show_eta
        self.output = output

        self.current = 0
        self.start_time: Optional[float] = None
        self._last_output_len = 0

    def start(self) -> None:
        """Start the progress tracker."""
        self.start_time = time.time()
        self.current = 0
        self._update_display()

    def update(self, current: Optional[int] = None, increment: int = 1) -> None:
        """Update progress.

        Args:
            current: Set current progress directly.
            increment: Increment current progress by this amount.
        """
        if current is not None:
            self.current = current
        else:
            self.current += increment

        self._update_display()

    def finish(self, message: Optional[str] = None) -> None:
        """Finish progress tracking.

        Args:
            message: Optional completion message.
        """
        self.current = self.total
        if message:
            self._clear_line()
            self.output.write(f"{message}\n")
        else:
            self._update_display()
            self.output.write("\n")
        self.output.flush()

    @property
    def percentage(self) -> float:
        """Get current percentage complete."""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    @property
    def eta_seconds(self) -> Optional[float]:
        """Get estimated time remaining in seconds."""
        if self.current == 0 or self.elapsed_seconds == 0:
            return None
        rate = self.current / self.elapsed_seconds
        remaining = self.total - self.current
        return remaining / rate if rate > 0 else None

    def _format_eta(self) -> str:
        """Format ETA as human-readable string."""
        eta = self.eta_seconds
        if eta is None:
            return "calculating..."

        if eta < 60:
            return f"{int(eta)}s"
        elif eta < 3600:
            minutes = int(eta / 60)
            seconds = int(eta % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(eta / 3600)
            minutes = int((eta % 3600) / 60)
            return f"{hours}h {minutes}m"

    def _clear_line(self) -> None:
        """Clear the current line."""
        if self._last_output_len > 0:
            self.output.write('\r' + ' ' * self._last_output_len + '\r')

    def _update_display(self) -> None:
        """Update the progress display."""
        self._clear_line()

        # Build progress string
        parts = [
            f"{self.description}...",
            f"{self.percentage:.1f}%",
            f"({self.current}/{self.total})",
        ]

        if self.show_eta and self.current > 0 and self.current < self.total:
            parts.append(f"ETA: {self._format_eta()}")

        line = " ".join(parts)
        self._last_output_len = len(line)

        self.output.write(f"\r{line}")
        self.output.flush()


class AnalysisProgress:
    """Multi-phase progress tracking for health analysis.

    Tracks progress across analysis phases:
    - Reading messages: 0-30%
    - Calculating metrics: 30-60%
    - Topic clustering: 60-80%
    - Generating report: 80-100%
    """

    PHASES = {
        "reading": (0, 30),
        "metrics": (30, 60),
        "topics": (60, 80),
        "report": (80, 100),
    }

    def __init__(self, output=sys.stdout, verbose: bool = False):
        """Initialize analysis progress.

        Args:
            output: Output stream.
            verbose: Show verbose progress output.
        """
        self.output = output
        self.verbose = verbose
        self.current_phase = ""
        self.phase_progress = 0.0
        self.start_time: Optional[float] = None

    def start(self) -> None:
        """Start progress tracking."""
        self.start_time = time.time()

    def set_phase(self, phase: str) -> None:
        """Set current phase.

        Args:
            phase: Phase name (reading, metrics, topics, report).
        """
        if phase not in self.PHASES:
            return

        self.current_phase = phase
        self.phase_progress = 0.0
        self._update_display()

    def update_phase_progress(self, progress: float) -> None:
        """Update progress within current phase.

        Args:
            progress: Progress within phase (0.0 to 1.0).
        """
        self.phase_progress = min(1.0, max(0.0, progress))
        self._update_display()

    @property
    def overall_percentage(self) -> float:
        """Get overall percentage complete."""
        if self.current_phase not in self.PHASES:
            return 0.0

        start, end = self.PHASES[self.current_phase]
        return start + (end - start) * self.phase_progress

    def _update_display(self) -> None:
        """Update the progress display."""
        if not self.verbose:
            return

        phase_names = {
            "reading": "Reading messages",
            "metrics": "Calculating metrics",
            "topics": "Clustering topics",
            "report": "Generating report",
        }

        phase_name = phase_names.get(self.current_phase, self.current_phase)
        line = f"\r{phase_name}... {self.overall_percentage:.0f}%"

        self.output.write(line)
        self.output.flush()

    def finish(self, message: str = "Complete") -> None:
        """Finish progress tracking.

        Args:
            message: Completion message.
        """
        if self.verbose:
            self.output.write(f"\r{message}{'':20}\n")
            self.output.flush()
