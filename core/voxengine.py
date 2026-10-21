"""
VoxCPM2 gọn nhẹ: gọi thẳng thư viện `voxcpm`, không cần giao diện gradio / funasr của bản demo.
Giữ nguyên chữ ký generate_tts_audio(...) mà routes/speech.py đang dùng.
"""

import re


class VoxEngine:
    def __init__(self, model_id="openbmb/VoxCPM2", device="auto"):
        import voxcpm
        from voxcpm.model.utils import resolve_runtime_device

        self._voxcpm = voxcpm
        self.device = resolve_runtime_device(device, "cuda")
        self.optimize = self.device.startswith("cuda")
        self._model_id = model_id
        self.model = None

    def load(self):
        if self.model is None:
            self.model = self._voxcpm.VoxCPM.from_pretrained(
                self._model_id,
                optimize=self.optimize,
                device=self.device,
                load_denoiser=False,  # bộ lọc ồn cần modelscope + tải thêm model; không bắt buộc
            )
        return self.model

    def generate_tts_audio(
        self,
        text_input,
        control_instruction="",
        reference_wav_path_input=None,
        prompt_text="",
        cfg_value_input=2.0,
        do_normalize=True,
        denoise=False,
        inference_timesteps=10,
        seed=None,
    ):
        model = self.load()
        text = (text_input or "").strip()
        if not text:
            raise ValueError("Chưa có văn bản để đọc")
        control = re.sub(r"[()（）]", "", (control_instruction or "")).strip()
        final_text = f"({control}){text}" if control else text

        audio_path = reference_wav_path_input or None
        prompt_text_clean = (prompt_text or "").strip() or None
        kwargs = dict(
            text=final_text,
            reference_wav_path=audio_path,
            cfg_value=float(cfg_value_input),
            inference_timesteps=inference_timesteps,
            normalize=do_normalize,
            denoise=denoise,
            seed=seed,
        )
        if prompt_text_clean and audio_path:
            kwargs["prompt_wav_path"] = audio_path
            kwargs["prompt_text"] = prompt_text_clean
        wav = model.generate(**kwargs)
        last_seed = getattr(model.tts_model, "last_successful_seed", seed)
        return model.tts_model.sample_rate, wav, last_seed
