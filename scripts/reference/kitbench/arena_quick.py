import sys,time,numpy as np,pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import QuantileTransformer
from sklearn.pipeline import make_pipeline
D=sys.argv[1]
def run(name, X, y, seed):
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.3,random_state=seed,stratify=y)
    out={}
    for mname,m in [("HGB",HistGradientBoostingClassifier(random_state=seed)),("RF",RandomForestClassifier(300,n_jobs=4,random_state=seed)),
                    ("MLP",make_pipeline(QuantileTransformer(output_distribution="normal",random_state=seed),MLPClassifier((256,256),early_stopping=True,max_iter=200,random_state=seed)))]:
        t=time.time(); m.fit(Xtr,ytr); out[mname]=(m.score(Xte,yte),time.time()-t)
    return out
for f in ["MagicTelescope","electricity","california","credit"]:
    df=pd.read_csv(f"{D}/{f}.csv"); y=df.iloc[:,-1].astype("category").cat.codes.values; X=df.iloc[:,:-1].values.astype(np.float32)
    for variant in ["base","+noise","rotated"]:
        Xv=X.copy(); rng=np.random.default_rng(0)
        if variant=="+noise": Xv=np.hstack([Xv,rng.normal(size=(len(Xv),Xv.shape[1]))]).astype(np.float32)
        if variant=="rotated":
            Xs=(Xv-Xv.mean(0))/(Xv.std(0)+1e-9); Q,_=np.linalg.qr(rng.normal(size=(Xv.shape[1],Xv.shape[1]))); Xv=(Xs@Q).astype(np.float32)
        r=run(f,Xv,y,0); print(f"{f:15s} {variant:8s} "+"  ".join(f"{k} {v[0]:.3f} ({v[1]:.1f}s)" for k,v in r.items()),flush=True)
