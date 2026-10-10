import time, sys
T = time.perf_counter
def t(label, f, n=1):
    s = T(); r = None
    for _ in range(n): r = f()
    print(f"{label}: {(T()-s)/n*1000:.2f} ms"); return r

s=T(); import numpy as np; print(f"import numpy {(T()-s)*1000:.0f} ms")
s=T(); from scipy.optimize import curve_fit; print(f"import scipy.optimize {(T()-s)*1000:.0f} ms")
s=T(); from sklearn.linear_model import LogisticRegression; from sklearn.gaussian_process import GaussianProcessRegressor; from sklearn.gaussian_process.kernels import Matern; print(f"import sklearn {(T()-s)*1000:.0f} ms")
s=T(); import optuna; print(f"import optuna {(T()-s)*1000:.0f} ms")
optuna.logging.set_verbosity(optuna.logging.WARNING)

rng = np.random.default_rng(0)
# curve fit: sigmoid in log-step (grokking shape)
x = np.linspace(0, 5, 400)  # log10 step
y = 0.01 + 0.99/(1+np.exp(-(x-3.8)*6)) + rng.normal(0, .02, x.size)
sig = lambda x, a, b, c, d: a + b/(1+np.exp(-(x-c)*d))
t("curve_fit sigmoid 400pts", lambda: curve_fit(sig, x, y, p0=[0,1,3,3], maxfev=5000), 20)
pw = lambda x, a, b, c: a - b*np.power(x+1e-3, -c)
t("curve_fit power-law 400pts", lambda: curve_fit(pw, x+1, y, p0=[1,1,0.5], maxfev=5000), 20)

# Optuna TPE ask/tell with 30 trials of history over 4 params
st = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=0))
def obj(tr):
    return tr.suggest_float("wd",1e-3,3,log=True)+tr.suggest_float("frac",.2,.8)+tr.suggest_float("lr",1e-4,1e-2,log=True)+tr.suggest_categorical("opt",["adamw","adam","sgd"]) .__len__()
s=T(); st.optimize(obj, n_trials=30); print(f"optuna TPE 30 trials total {(T()-s)*1000:.0f} ms")
t("optuna TPE 1 ask at 30 history", lambda: st.tell(tr:=st.ask({"wd":optuna.distributions.FloatDistribution(1e-3,3,log=True),"frac":optuna.distributions.FloatDistribution(.2,.8)}), 1.0), 10)

# sklearn GP on 40 points, 4 dims + EI over 2000 candidates
X = rng.random((40,4)); Y = rng.random(40)
gp = GaussianProcessRegressor(Matern(nu=2.5), normalize_y=True, n_restarts_optimizer=3)
t("sklearn GP fit 40x4", lambda: gp.fit(X,Y), 5)
C = rng.random((2000,4))
t("GP predict 2000 cands w/ std", lambda: gp.predict(C, return_std=True), 5)

# LinUCB: 8 arms, d=16
d=16; A=[np.eye(d) for _ in range(8)]; b=[np.zeros(d) for _ in range(8)]
def linucb():
    xc = rng.random(d)
    p=[ (np.linalg.solve(A[k], b[k])@xc + 1.0*np.sqrt(xc@np.linalg.solve(A[k], xc))) for k in range(8)]
    k=int(np.argmax(p)); A[k]+=np.outer(xc,xc); b[k]+=xc*rng.random()
t("LinUCB select+update 8 arms d=16", linucb, 1000)

# logistic regression on 384-d embeddings
Xe = rng.normal(size=(300,384)); ye = rng.integers(0,6,300)
lr = t("LogReg fit 300x384 6 classes", lambda: LogisticRegression(max_iter=500).fit(Xe,ye), 3)
t("LogReg predict 1", lambda: lr.predict_proba(Xe[:1]), 100)

# Fourier analysis of grokked model: W_E (113x128), logits over all pairs 113^2 x 113
p=113
WE = rng.normal(size=(p,128)).astype(np.float32)
def fourier_embed():
    F = np.fft.rfft(WE, axis=0)            # (57,128)
    norms = np.linalg.norm(F, axis=1)
    return np.argsort(norms)[-5:]
t("FFT of W_E + key freqs", fourier_embed, 100)
logits = rng.normal(size=(p,p,p)).astype(np.float32)  # (a,b,c)
def restricted():
    F = np.fft.fft2(logits, axes=(0,1))
    keys=[14,35,41,42,52]; M=np.zeros((p,p),bool); M[0,0]=True
    for k in keys:
        for (i,j) in [(k,k),(p-k,p-k),(k,0),(0,k)]: M[i,j]=True; M[(p-i)%p,(p-j)%p]=True
    Fr = F*M[:,:,None]
    return np.fft.ifft2(Fr, axes=(0,1)).real
t("2D DFT restricted-logits on 113^3 tensor", restricted, 3)

s=T(); from fastembed import TextEmbedding; print(f"import fastembed {(T()-s)*1000:.0f} ms")
s=T(); m = TextEmbedding("BAAI/bge-small-en-v1.5"); print(f"fastembed load bge-small (cache state: see run#) {(T()-s)*1000:.0f} ms")
t("embed 1 short text (first call)", lambda: list(m.embed(["RuntimeError: CUDA out of memory"])), 1)
t("embed 1 short text (warm)", lambda: list(m.embed(["RuntimeError: CUDA out of memory. Tried to allocate"])), 20)
t("embed 32 tracebacks (~60 tok)", lambda: list(m.embed(["Traceback (most recent call last): File train.py line 42 in step loss.backward() RuntimeError: element 0 of tensors does not require grad"]*32)), 3)
