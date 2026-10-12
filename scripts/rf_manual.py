"""Random Forest regresi yang diimplementasikan sendiri (hanya NumPy).

Komponen (Breiman, 2001):
  - Pohon regresi CART: setiap simpul dibagi pada fitur dan ambang yang paling
    menurunkan jumlah kuadrat galat (SSE), sampai kedalaman maksimum atau
    jumlah sampel minimum per daun tercapai. Nilai daun = rata-rata target.
  - Bootstrap: setiap pohon dilatih pada sampel acak dengan pengembalian.
  - Subset fitur acak: pada setiap simpul hanya `maks_fitur` fitur yang dipertimbangkan.
  - Prediksi forest = rata-rata prediksi seluruh pohon.
  - Feature importance = total penurunan SSE per fitur, dinormalisasi menjadi 1.
Juga disediakan pembagi leave-one-group-out dan metrik R², RMSE, MAPE.
"""
import numpy as np


class PohonRegresi:
    def __init__(self, kedalaman_maks=6, min_daun=3, maks_fitur=None, rng=None):
        self.kedalaman_maks, self.min_daun, self.maks_fitur = kedalaman_maks, min_daun, maks_fitur
        self.rng = rng or np.random.default_rng()

    def fit(self, X, y):
        self.n_fitur = X.shape[1]
        self.penting = np.zeros(self.n_fitur)
        # simpul disimpan sebagai daftar: fitur (-1 = daun), ambang, anak kiri, anak kanan, nilai
        self.fitur, self.ambang, self.kiri, self.kanan, self.nilai = [], [], [], [], []
        self._bangun(X, y, 0)
        self.fitur, self.ambang = np.array(self.fitur), np.array(self.ambang)
        self.kiri, self.kanan, self.nilai = np.array(self.kiri), np.array(self.kanan), np.array(self.nilai)
        return self

    def _simpul_baru(self, nilai):
        for daftar, v in ((self.fitur, -1), (self.ambang, 0.0), (self.kiri, -1), (self.kanan, -1), (self.nilai, nilai)):
            daftar.append(v)
        return len(self.nilai) - 1

    def _split_terbaik(self, X, y):
        """Cari (fitur, ambang, penurunan SSE) terbaik di antara subset fitur acak."""
        n = len(y)
        sse_induk = ((y - y.mean()) ** 2).sum()
        k = self.maks_fitur or self.n_fitur
        terbaik, dicoba = (None, None, 0.0), 0
        # Fitur diperiksa dalam urutan acak. Fitur yang nilainya seragam di simpul ini tidak dihitung,
        # dan pencarian berlanjut ke fitur berikutnya sampai minimal k fitur diperiksa DAN satu split
        # sah ditemukan (aturan yang sama dengan Breiman/CART pada umumnya).
        for f in self.rng.permutation(self.n_fitur):
            if dicoba >= k and terbaik[0] is not None:
                break
            # kelompokkan per nilai unik (terurut), lalu jumlah kumulatif → SSE kiri/kanan setiap ambang
            nilai, inv = np.unique(X[:, f], return_inverse=True)
            if len(nilai) < 2:
                continue
            dicoba += 1
            cn = np.cumsum(np.bincount(inv))[:-1]                # jumlah sampel di kiri untuk tiap ambang
            s1 = np.cumsum(np.bincount(inv, weights=y))[:-1]
            s2 = np.cumsum(np.bincount(inv, weights=y ** 2))[:-1]
            sah = (cn >= self.min_daun) & (n - cn >= self.min_daun)
            if not sah.any():
                continue
            cn, s1, s2 = cn[sah], s1[sah], s2[sah]
            sse_kiri = s2 - s1 ** 2 / cn
            sse_kanan = (y ** 2).sum() - s2 - (y.sum() - s1) ** 2 / (n - cn)
            turun = sse_induk - (sse_kiri + sse_kanan)
            j = np.argmax(turun)
            if turun[j] > terbaik[2]:
                a = np.flatnonzero(sah)[j]
                terbaik = (f, (nilai[a] + nilai[a + 1]) / 2, turun[j])  # ambang = titik tengah dua nilai
        return terbaik

    def _bangun(self, X, y, kedalaman):
        simpul = self._simpul_baru(y.mean())
        if kedalaman >= self.kedalaman_maks or len(y) < 2 * self.min_daun:
            return simpul
        f, t, turun = self._split_terbaik(X, y)
        if f is None or turun <= 1e-12:
            return simpul
        self.penting[f] += turun
        m = X[:, f] <= t
        self.fitur[simpul], self.ambang[simpul] = f, t
        self.kiri[simpul] = self._bangun(X[m], y[m], kedalaman + 1)
        self.kanan[simpul] = self._bangun(X[~m], y[~m], kedalaman + 1)
        return simpul

    def predict(self, X):
        simpul = np.zeros(len(X), dtype=int)
        for _ in range(self.kedalaman_maks):                    # turunkan semua sampel satu tingkat sekaligus
            f = self.fitur[simpul]
            aktif = f >= 0
            if not aktif.any():
                break
            ke_kiri = X[np.arange(len(X)), np.where(aktif, f, 0)] <= self.ambang[simpul]
            simpul = np.where(aktif, np.where(ke_kiri, self.kiri[simpul], self.kanan[simpul]), simpul)
        return self.nilai[simpul]


class RandomForestManual:
    def __init__(self, n_pohon=300, kedalaman_maks=6, min_daun=3, maks_fitur=2, seed=42):
        self.n_pohon, self.kedalaman_maks, self.min_daun = n_pohon, kedalaman_maks, min_daun
        self.maks_fitur, self.seed = maks_fitur, seed

    def fit(self, X, y):
        X, y = np.asarray(X, float), np.asarray(y, float)
        rng = np.random.default_rng(self.seed)
        self.pohon = []
        for _ in range(self.n_pohon):
            b = rng.integers(0, len(y), len(y))                   # sampel bootstrap
            self.pohon.append(PohonRegresi(self.kedalaman_maks, self.min_daun, self.maks_fitur, rng).fit(X[b], y[b]))
        total = sum(p.penting / p.penting.sum() for p in self.pohon if p.penting.sum() > 0)
        self.feature_importances_ = total / total.sum()
        return self

    def predict(self, X):
        X = np.asarray(X, float)
        return np.mean([p.predict(X) for p in self.pohon], axis=0)


def leave_one_group_out(grup):
    """Hasilkan (indeks latih, indeks uji) dengan satu kelompok ditahan per lipatan."""
    grup = np.asarray(grup)
    for g in np.unique(grup):
        yield np.flatnonzero(grup != g), np.flatnonzero(grup == g)


def r2(y, p):
    return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def rmse(y, p):
    return float(np.sqrt(((y - p) ** 2).mean()))


def mape(y, p):
    return float(np.mean(np.abs((y - p) / y)))
