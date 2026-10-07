import sys, os
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/root/.ccr/ca-bundle.crt'); os.environ.setdefault('SSL_CERT_FILE', '/root/.ccr/ca-bundle.crt')
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1] if len(sys.argv) > 1 else 'medium', device='cpu', compute_type='int8')
import subprocess, numpy as np
def load(fn):
    raw = subprocess.check_output(['ffmpeg','-v','error','-i',fn,'-ac','1','-ar','16000','-f','f32le','-'])
    return np.frombuffer(raw, np.float32)
def tr(fn, prompt=None):
    segs, _ = m.transcribe(load(fn), language='zh', beam_size=5, initial_prompt=prompt, vad_filter=False)
    return ''.join(s.text for s in segs).strip()
if __name__ == '__main__':
    for fn in sys.argv[2:]: print(fn, tr(fn))
