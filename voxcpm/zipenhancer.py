"""
ZipEnhancer Module - Audio Denoising Enhancer

Provides on-demand import ZipEnhancer functionality for audio denoising processing.
Related dependencies are imported only when denoising functionality is needed.
"""

import logging
import os
import shutil
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

logger = logging.getLogger(__name__)


class ZipEnhancer:
    """ZipEnhancer Audio Denoising Enhancer"""

    def __init__(
        self, model_path: str = "iic/speech_zipenhancer_ans_multiloss_16k_base"
    ):
        """
        Initialize ZipEnhancer
        Args:
            model_path: ModelScope model path or local path
        """
        self.model_path = model_path
        try:
            self._pipeline = pipeline(
                Tasks.acoustic_noise_suppression, model=self.model_path
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ZipEnhancer pipeline: {e}")
            self._pipeline = None

    def _normalize_loudness(self, wav_path: str):
        """
        Audio loudness normalization using soundfile & numpy (zero torchcodec dependency)
        Args:
            wav_path: Audio file path
        """
        try:
            data, sr = sf.read(wav_path)
            max_val = np.max(np.abs(data))
            if max_val > 0:
                normalized = data / max_val * 0.95
                sf.write(wav_path, normalized, sr)
        except Exception as e:
            logger.warning(f"Loudness normalization skipped safely: {e}")

    def enhance(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        normalize_loudness: bool = True,
    ) -> str:
        """
        Audio denoising enhancement
        Args:
            input_path: Input audio file path
            output_path: Output audio file path (optional, creates temp file by default)
            normalize_loudness: Whether to perform loudness normalization
        Returns:
            str: Output audio file path
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input audio file does not exist: {input_path}")

        if output_path is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                output_path = tmp_file.name

        try:
            if hasattr(self, "_pipeline") and self._pipeline is not None:
                self._pipeline(input_path, output_path=output_path)
            else:
                shutil.copyfile(input_path, output_path)

            if normalize_loudness:
                self._normalize_loudness(output_path)
            return output_path
        except Exception as e:
            logger.warning(
                f"ZipEnhancer processing encountered error ({e}). Falling back to raw reference audio."
            )
            try:
                shutil.copyfile(input_path, output_path)
                if normalize_loudness:
                    self._normalize_loudness(output_path)
            except Exception as copy_err:
                logger.error(f"Fallback audio copy failed: {copy_err}")
                return input_path
            return output_path
