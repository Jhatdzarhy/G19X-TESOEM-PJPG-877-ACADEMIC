"""Isolation Forest implementado con numpy (CC-07; implementacion propia por CC-18).

Algoritmo original de Liu, Ting y Zhou (2008), "Isolation Forest", IEEE ICDM:
  - Cada arbol se construye con una submuestra aleatoria de psi = min(256, n) registros.
  - En cada nodo se elige al azar una variable que no sea constante y un punto de corte
    uniforme entre su minimo y su maximo; se divide hasta aislar el registro o llegar a
    la altura limite ceil(log2(psi)).
  - Largo de camino h(x): profundidad de la hoja mas c(tamano de la hoja), donde
    c(n) = 2 H(n-1) - 2 (n-1)/n es el largo promedio de una busqueda fallida en un arbol
    binario y H(i) ~ ln(i) + 0.5772156649 (constante de Euler).
  - Score s(x) = 2 ^ (-E[h(x)] / c(psi)); cerca de 1 es anomalo, cerca de 0.5 o menos es normal.
  - Umbral: percentil (1 - contaminacion) de los scores de entrenamiento.

Misma interfaz que sklearn.ensemble.IsolationForest en lo que usa este proyecto:
fit, score_samples (negativo del score, como sklearn) y predict (-1 anomalo, 1 normal).
"""
import math

import numpy as np

EULER = 0.5772156649


def _c(n):
    """Largo promedio de camino para n registros (vectorizado)."""
    n = np.asarray(n, dtype=float)
    salida = np.zeros_like(n)
    mayor = n > 2
    salida[mayor] = 2.0 * (np.log(n[mayor] - 1.0) + EULER) - 2.0 * (n[mayor] - 1.0) / n[mayor]
    salida[n == 2] = 1.0
    return salida


class IsolationForest:
    def __init__(self, n_estimators=100, max_samples=256, contamination=0.1, random_state=None):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.random_state = random_state

    # cada arbol se guarda como arreglos: variable, corte, hijo izquierdo, hijo derecho, ajuste de hoja
    def _arbol(self, x, rng, limite):
        var, corte, izq, der, hoja = [], [], [], [], []

        def nodo(indices, profundidad):
            k = len(var)
            var.append(-1); corte.append(0.0); izq.append(-1); der.append(-1); hoja.append(0.0)
            datos = x[indices]
            if profundidad >= limite or len(indices) <= 1:
                hoja[k] = profundidad + float(_c([len(indices)])[0])
                return k
            minimos, maximos = datos.min(axis=0), datos.max(axis=0)
            candidatas = np.flatnonzero(maximos > minimos)
            if candidatas.size == 0:
                hoja[k] = profundidad + float(_c([len(indices)])[0])
                return k
            j = int(rng.choice(candidatas))
            c = rng.uniform(minimos[j], maximos[j])
            mascara = datos[:, j] < c
            var[k], corte[k] = j, c
            izq[k] = nodo(indices[mascara], profundidad + 1)
            der[k] = nodo(indices[~mascara], profundidad + 1)
            return k

        nodo(np.arange(len(x)), 0)
        return tuple(np.array(a) for a in (var, corte, izq, der, hoja))

    def fit(self, x):
        x = np.asarray(x, dtype=float)
        rng = np.random.default_rng(self.random_state)
        self.psi_ = min(self.max_samples, len(x))
        limite = math.ceil(math.log2(max(self.psi_, 2)))
        self.arboles_ = [self._arbol(x[rng.choice(len(x), self.psi_, replace=False)], rng, limite)
                         for _ in range(self.n_estimators)]
        self.umbral_ = np.quantile(self.score_samples(x), self.contamination)
        return self

    def _largo_camino(self, x):
        total = np.zeros(len(x))
        for var, corte, izq, der, hoja in self.arboles_:
            actual = np.zeros(len(x), dtype=int)
            while True:
                internos = var[actual] >= 0
                if not internos.any():
                    break
                n = actual[internos]
                va_izq = x[internos, var[n]] < corte[n]
                actual[internos] = np.where(va_izq, izq[n], der[n])
            total += hoja[actual]
        return total / len(self.arboles_)

    def score_samples(self, x):
        """Negativo del score de anomalia (convencion de sklearn: mas bajo es mas anomalo)."""
        x = np.asarray(x, dtype=float)
        return -np.power(2.0, -self._largo_camino(x) / float(_c([self.psi_])[0]))

    def predict(self, x):
        return np.where(self.score_samples(x) < self.umbral_, -1, 1)