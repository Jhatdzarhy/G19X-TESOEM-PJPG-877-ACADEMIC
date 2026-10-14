/*
 * Resumen ejecutivo (diseno CC-10): Estado de la cadena, Que atender hoy y
 * Demanda y pronostico. Lee /api/estaciones, /api/recomendaciones/atender-hoy y
 * /api/pronostico (ApiLecturaServlet, CC-21). Todo se inserta con textContent.
 * Se actualiza cada 60 segundos mientras la pestana esta visible (CC-09).
 */
(function () {
    'use strict';

    var SC = window.SC;
    var AZUL_DATO = '#1A56A8';
    var GRIS_META = '#8a94a6';
    var REFRESCO_MS = 60000;
    var grafica = null;

    /* ------------------------------------------------------ Estado de la cadena */

    function textoMeta(e) {
        var signo = e.sentido === 'menor' ? '≤' : '≥';
        return SC.ortografia(e.etiqueta) + ' · meta ' + signo + ' ' + SC.numero(e.meta, e.meta % 1 ? 1 : 0) +
            ' ' + SC.unidadVisible(e.unidad);
    }

    function textoVariacion(e) {
        if (e.variacion_vs_anterior === null || e.variacion_vs_anterior === undefined) { return ''; }
        var unidad = e.unidad === '%' ? ' pts' : ' ' + SC.unidadVisible(e.unidad);
        return SC.conSigno(e.variacion_vs_anterior, 1) + unidad + ' contra los 30 días anteriores';
    }

    function textoSecundario(e) {
        var s = e.secundario;
        if (!s) { return ''; }
        if (e.clave === 'inventario') {
            return 'Rotación ' + SC.numero(s.valor, 1) + ' veces al año · ' + SC.numero(s.doh, 0) + ' días de inventario';
        }
        if (s.unidad === 'MXN') {
            return SC.ortografia(s.etiqueta) + ' $' + SC.numero(s.valor, 2) + ' MXN';
        }
        var valor = /variaci/i.test(s.etiqueta) ? SC.conSigno(s.valor, 2) : SC.numero(s.valor, 1);
        return SC.ortografia(s.etiqueta) + ' ' + valor + ' ' + s.unidad;
    }

    /** Minigrafica SVG de 30 dias con la meta punteada; se construye con nodos, sin HTML. */
    function minigrafica(e) {
        var NS = 'http://www.w3.org/2000/svg';
        var ancho = 200, alto = 48, margen = 4;
        var valores = (e.serie || []).map(function (p) { return p.valor; });
        var svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('viewBox', '0 0 ' + ancho + ' ' + alto);
        svg.setAttribute('class', 'minigrafica');
        svg.setAttribute('role', 'img');
        var titulo = document.createElementNS(NS, 'title');
        titulo.textContent = SC.ortografia(e.etiqueta) + ' diario de los últimos 30 días; del ' +
            SC.numero(valores[0]) + ' al ' + SC.numero(valores[valores.length - 1]) +
            ' ' + SC.unidadVisible(e.unidad) + ', meta ' + SC.numero(e.meta);
        svg.appendChild(titulo);
        if (valores.length < 2) { return svg; }

        var todos = valores.concat([e.meta]);
        var min = Math.min.apply(null, todos), max = Math.max.apply(null, todos);
        var rango = (max - min) || 1;
        function y(v) { return margen + (alto - 2 * margen) * (1 - (v - min) / rango); }
        function x(i) { return margen + (ancho - 2 * margen) * i / (valores.length - 1); }

        var meta = document.createElementNS(NS, 'line');
        meta.setAttribute('x1', margen); meta.setAttribute('x2', ancho - margen);
        meta.setAttribute('y1', y(e.meta)); meta.setAttribute('y2', y(e.meta));
        meta.setAttribute('class', 'minigrafica-meta');
        svg.appendChild(meta);

        var linea = document.createElementNS(NS, 'polyline');
        linea.setAttribute('points', valores.map(function (v, i) { return x(i).toFixed(1) + ',' + y(v).toFixed(1); }).join(' '));
        linea.setAttribute('class', 'minigrafica-real');
        svg.appendChild(linea);

        var punto = document.createElementNS(NS, 'circle');
        punto.setAttribute('cx', x(valores.length - 1)); punto.setAttribute('cy', y(valores[valores.length - 1]));
        punto.setAttribute('r', 3);
        punto.setAttribute('class', 'minigrafica-punto');
        svg.appendChild(punto);
        return svg;
    }

    function pintarEstaciones(datos) {
        var cont = document.getElementById('estaciones');
        SC.vaciar(cont);
        datos.estaciones.forEach(function (e) {
            var tarjeta = SC.el('article', 'estacion estacion-' + (SC.ESTADOS[e.estado] || SC.ESTADOS.SIN_DATOS).clase);
            var cabeza = SC.el('div', 'estacion-cabeza');
            cabeza.appendChild(SC.el('h3', 'estacion-nombre', e.nombre));
            cabeza.appendChild(SC.insigniaEstado(e.estado));
            tarjeta.appendChild(cabeza);

            var valor = SC.el('p', 'estacion-valor');
            valor.appendChild(SC.el('span', 'estacion-numero', SC.numero(e.valor, 1)));
            valor.appendChild(SC.el('span', 'estacion-unidad', e.unidad === '%' ? '%' : ' ' + SC.unidadVisible(e.unidad)));
            tarjeta.appendChild(valor);
            tarjeta.appendChild(SC.el('p', 'estacion-meta', textoMeta(e)));
            tarjeta.appendChild(minigrafica(e));
            tarjeta.appendChild(SC.el('p', 'estacion-detalle', textoVariacion(e)));
            var secundario = textoSecundario(e);
            if (secundario) { tarjeta.appendChild(SC.el('p', 'estacion-detalle', secundario)); }
            cont.appendChild(tarjeta);
        });

        document.getElementById('resumen-periodo').textContent = 'Últimos ' + datos.dias + ' días · del ' +
            SC.fecha(datos.desde, false) + ' al ' + SC.fecha(datos.fecha_corte) + ' (fecha de corte)';
        document.getElementById('resumen-actualizado').textContent = 'Calculado a las ' + SC.hora(datos.generado);
    }

    /* ---------------------------------------------------------- Que atender hoy */

    var MODULOS = {
        COMPRAS: 'Compras', INVENTARIOS: 'Inventarios', LOGISTICA: 'Logística',
        ALMACENES: 'Almacenes', PROVEEDORES: 'Proveedores'
    };

    function pintarAtender(datos) {
        var lista = document.getElementById('atender');
        SC.vaciar(lista);
        var items = (datos.atender_hoy || []).slice(0, 5);
        document.getElementById('atender-vacio').hidden = items.length > 0;
        document.getElementById('atender-contador').textContent = items.length + (items.length === 1 ? ' prioridad' : ' prioridades');

        items.forEach(function (r, i) {
            var li = SC.el('li', 'atender-item atender-' + (SC.ESTADOS[r.severidad] || SC.ESTADOS.SIN_DATOS).clase);
            var enlace = SC.el('a', 'atender-enlace');
            enlace.href = SC.CTX + '/soluciones?id=' + encodeURIComponent(r.recomendacion_id);

            enlace.appendChild(SC.el('span', 'atender-rango', String(i + 1)));
            var texto = SC.el('div', 'atender-texto');
            texto.appendChild(SC.el('span', 'atender-titulo', SC.ortografia(r.titulo)));
            texto.appendChild(SC.el('span', 'atender-sub', 'Recomendación: ' + SC.ortografia(r.solucion_recomendada)));
            texto.appendChild(SC.el('span', 'atender-sub', (MODULOS[r.modulo] || SC.ortografia(r.modulo)) +
                ' · confianza ' + SC.numero(r.confianza * 100, 0) + ' %'));
            enlace.appendChild(texto);

            var impacto = SC.el('div', 'atender-impacto');
            impacto.appendChild(SC.el('span', 'atender-monto', SC.pesos(r.impacto_estimado_mxn)));
            impacto.appendChild(SC.insigniaEstado(r.severidad));
            enlace.appendChild(impacto);

            li.appendChild(enlace);
            lista.appendChild(li);
        });
    }

    /* ------------------------------------------------------ Demanda y pronostico */

    function pintarDemanda(datos) {
        document.getElementById('demanda-total').textContent = SC.numero(datos.total_proyectado, 0) + ' u';
        document.getElementById('demanda-mape').textContent = SC.numero(datos.mape_pct, 1) + ' %';
        document.getElementById('demanda-sub').textContent = 'Unidades diarias, ' +
            SC.ortografia(datos.producto === 'Todos los SKU' ? 'todos los SKU' : datos.producto) + ' · Holt-Winters semanal';
        document.getElementById('demanda-variacion').textContent = SC.conSigno(datos.variacion_pct, 1) +
            ' % contra los 14 días anteriores';

        var real = (datos.real || []).slice(-28);
        var pron = datos.pronostico || [];
        var etiquetas = real.map(function (p) { return SC.fecha(p.fecha, false); })
            .concat(pron.map(function (p) { return SC.fecha(p.fecha, false); }));
        var nulosReal = pron.map(function () { return null; });
        var nulosPron = real.map(function () { return null; });
        // El pronostico arranca en el ultimo dia real para que la linea sea continua.
        var ultimo = real.length ? real[real.length - 1].valor : null;
        var serieReal = real.map(function (p) { return p.valor; }).concat(nulosReal);
        var seriePron = nulosPron.slice(0, -1).concat([ultimo]).concat(pron.map(function (p) { return p.valor; }));
        var serieSup = nulosPron.slice(0, -1).concat([ultimo]).concat(pron.map(function (p) { return p.superior; }));
        var serieInf = nulosPron.slice(0, -1).concat([ultimo]).concat(pron.map(function (p) { return p.inferior; }));

        var conjuntos = [
            { label: 'Intervalo 90 % (superior)', data: serieSup, borderWidth: 0, pointRadius: 0,
              backgroundColor: 'rgba(26, 86, 168, 0.12)', fill: '+1', spanGaps: false },
            { label: 'Intervalo 90 % (inferior)', data: serieInf, borderWidth: 0, pointRadius: 0, fill: false },
            { label: 'Real', data: serieReal, borderColor: AZUL_DATO, borderWidth: 2, pointRadius: 0,
              pointHoverRadius: 4, tension: 0.25, fill: false },
            { label: 'Pronóstico', data: seriePron, borderColor: AZUL_DATO, borderWidth: 2, borderDash: [6, 4],
              pointRadius: 0, pointHoverRadius: 4, tension: 0.25, fill: false }
        ];

        if (grafica) {
            grafica.data.labels = etiquetas;
            grafica.data.datasets.forEach(function (d, i) { d.data = conjuntos[i].data; });
            grafica.update('none');
            return;
        }
        if (!window.Chart) {
            mostrarError('No se pudo cargar la biblioteca de gráficas (Chart.js). Revisa la conexión a internet.');
            return;
        }
        window.Chart.defaults.font.family = 'Barlow, system-ui, sans-serif';
        window.Chart.defaults.color = '#5b6474';
        grafica = new window.Chart(document.getElementById('grafica-demanda'), {
            type: 'line',
            data: { labels: etiquetas, datasets: conjuntos },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        filter: function (item) { return item.raw !== null && item.dataset.label.indexOf('Intervalo') !== 0; },
                        callbacks: {
                            label: function (item) { return item.dataset.label + ': ' + SC.numero(item.raw, 0) + ' u'; },
                            afterBody: function (items) {
                                var i = items.length ? items[0].dataIndex : -1;
                                var sup = serieSup[i], inf = serieInf[i];
                                return i >= real.length && sup !== null
                                    ? 'Intervalo 90 %: ' + SC.numero(inf, 0) + ' a ' + SC.numero(sup, 0) + ' u' : '';
                            }
                        }
                    }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                    y: { grid: { color: '#e8ebf0' }, border: { display: false },
                         ticks: { maxTicksLimit: 5, callback: function (v) { return SC.numero(v, 0); } } }
                }
            }
        });
    }

    /* ----------------------------------------------------------------- carga */

    function mostrarError(mensaje) {
        var aviso = document.getElementById('resumen-error');
        aviso.textContent = mensaje;
        aviso.hidden = false;
    }

    function cargar() {
        document.getElementById('resumen-error').hidden = true;
        return Promise.all([
            SC.api('/estaciones').then(pintarEstaciones),
            SC.api('/recomendaciones/atender-hoy').then(pintarAtender),
            SC.api('/pronostico').then(pintarDemanda)
        ]).catch(function (err) {
            if (err && err.estado !== 401) { mostrarError(err.message || 'No se pudieron cargar los datos.'); }
        });
    }

    cargar();
    setInterval(function () {
        if (!document.hidden) { cargar(); }
    }, REFRESCO_MS);

    window.SC_RESUMEN = { textoMeta: textoMeta, textoVariacion: textoVariacion, textoSecundario: textoSecundario };
}());