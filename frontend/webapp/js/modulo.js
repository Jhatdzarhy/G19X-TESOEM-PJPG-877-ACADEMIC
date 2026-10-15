/*
 * Vistas por modulo del dashboard (PDR seccion 6; diseno CC-10 y CC-24).
 *
 * Cada modulo sigue el mismo orden: indicadores del modulo (mismas cifras del Resumen, de
 * /api/kpis y /api/estaciones), una grafica principal, una tabla de detalle y los casos
 * abiertos del Centro de soluciones del modulo. Graficas primero; azul solo para datos;
 * estados siempre con texto. Todo se inserta con textContent (prevencion de XSS).
 * Se actualiza cada 60 segundos mientras la pestana esta visible (CC-09).
 */
(function () {
    'use strict';

    var SC = window.SC;
    var raiz = document.getElementById('modulo');
    if (!SC || !raiz) { return; }
    var MODULO = raiz.getAttribute('data-modulo');
    var AZUL = '#1A56A8';
    var SERIES = ['#1A56A8', '#0f172a', '#8a94a6'];
    var GRIS = '#8a94a6';
    var REFRESCO_MS = 60000;
    var grafica = null;

    function $(id) { return document.getElementById(id); }

    /* ---------------------------------------------------------------- formatos */

    function valorKpi(k) {
        if (k.valor === null || k.valor === undefined) { return 'Sin datos'; }
        switch (k.unidad) {
            case '%': return SC.numero(k.valor, 1) + ' %';
            case 'dias': return SC.numero(k.valor, 1) + ' días';
            case 'MXN': return k.clave === 'impacto_tc' ? SC.pesos(k.valor) + ' MXN' : '$' + SC.numero(k.valor, 2) + ' MXN';
            case 'veces al ano': return SC.numero(k.valor, 1) + ' veces al año';
            case '0 a 100': return SC.numero(k.valor, 1) + ' de 100';
            default: return SC.numero(k.valor, 1) + ' ' + SC.unidadVisible(k.unidad);
        }
    }

    function textoMeta(k) {
        if (k.meta === null || k.meta === undefined) { return 'Indicador informativo, sin meta'; }
        var unidad = k.unidad === '%' ? ' %' : k.unidad === '0 a 100' ? '' : ' ' + SC.unidadVisible(k.unidad);
        return 'Meta ' + (k.sentido === 'menor' ? '≤ ' : '≥ ') + SC.numero(k.meta, k.meta % 1 ? 1 : 0) + unidad +
            (k.umbral_critico !== null && k.umbral_critico !== undefined
                ? ' · crítico ' + (k.sentido === 'menor' ? '> ' : '< ') + SC.numero(k.umbral_critico, k.umbral_critico % 1 ? 1 : 0) + unidad
                : '');
    }

    function insignia(texto, clase) {
        return SC.el('span', 'insignia ' + clase, texto);
    }

    var COBERTURA = {
        SIN_STOCK: ['Sin stock', 'estado-critico'], BAJO: ['Bajo', 'estado-atencion'],
        EXCESO: ['Exceso', 'estado-atencion'], NORMAL: ['Normal', 'estado-ok']
    };
    var ENVIO = {
        EN_TRANSITO: ['En tránsito', 'estado-neutro'], ATRASADO: ['Atrasado', 'estado-atencion'],
        A_TIEMPO: ['A tiempo', 'estado-ok'], TARDIO: ['Tardío', 'estado-atencion']
    };
    var NIVEL = { BAJO: ['Bajo', 'estado-ok'], MEDIO: ['Medio', 'estado-atencion'], ALTO: ['Alto', 'estado-critico'] };
    var CLIMA = { DESPEJADO: 'Despejado', LLUVIA: 'Lluvia', LLUVIA_FUERTE: 'Lluvia fuerte', TORMENTA: 'Tormenta' };
    var MODULOS = {
        resumen: 'Resumen', compras: 'Compras', inventarios: 'Inventarios', logistica: 'Logística y transporte',
        almacenes: 'Almacenes', proveedores: 'Proveedores', ia: 'Inteligencia artificial'
    };
    var SEVERIDAD = { INFO: ['Informativo', 'estado-neutro'], ATENCION: ['Atención', 'estado-atencion'], CRITICO: ['Crítico', 'estado-critico'] };

    function corto(almacen) { return SC.ortografia(String(almacen || '').replace(/^Almacen /, '')); }

    /* ----------------------------------------------------------------- piezas */

    function encabezado(sub, d) {
        $('modulo-sub').textContent = sub;
        $('modulo-origen').textContent = d && d.origen === 'SIMULADO Y REAL' ? 'Simulado y real' : 'Datos simulados';
        $('modulo-actualizado').textContent = 'Calculado a las ' + new Date().toTimeString().slice(0, 5);
    }

    function periodo(d) {
        return 'Últimos ' + d.dias + ' días · del ' + SC.fecha(d.desde, false) + ' al ' + SC.fecha(d.fecha_corte) + ' (fecha de corte)';
    }

    function pintarKpis(lista) {
        var cont = $('modulo-kpis');
        SC.vaciar(cont);
        cont.hidden = !lista;
        if (!lista) { return; }
        if (!lista.length) {
            cont.appendChild(SC.el('p', 'aviso aviso-info', 'Todos los indicadores están en meta.'));
            return;
        }
        lista.forEach(function (k) {
            var t = SC.el('article', 'kpi-modulo kpi-' + (SC.ESTADOS[k.estado] || SC.ESTADOS.SIN_DATOS).clase);
            var cabeza = SC.el('div', 'kpi-cabeza');
            cabeza.appendChild(SC.el('h3', 'kpi-nombre', SC.ortografia(k.nombre)));
            cabeza.appendChild(SC.insigniaEstado(k.estado));
            t.appendChild(cabeza);
            t.appendChild(SC.el('p', 'kpi-valor', valorKpi(k)));
            t.appendChild(SC.el('p', 'kpi-meta', textoMeta(k)));
            t.appendChild(SC.el('p', 'kpi-origen', k.origen === 'SIMULADO Y REAL' ? 'Simulado y real' : 'Simulado'));
            cont.appendChild(t);
        });
    }

    function seccionGrafica(titulo, sub, nota, etiqueta) {
        $('modulo-grafica-caja').hidden = !titulo;
        if (grafica) { grafica.destroy(); grafica = null; }
        if (!titulo) { return null; }
        $('modulo-grafica-titulo').textContent = titulo;
        $('modulo-grafica-sub').textContent = sub || '';
        $('modulo-grafica-nota').textContent = nota || '';
        var lienzo = $('modulo-grafica');
        lienzo.setAttribute('aria-label', etiqueta || titulo);
        return lienzo;
    }

    /** Lineas de referencia punteadas (meta o umbral) con su etiqueta, dibujadas sobre la grafica. */
    var lineasReferencia = {
        id: 'lineasReferencia',
        afterDatasetsDraw: function (chart, args, opciones) {
            var area = chart.chartArea, ctx = chart.ctx;
            ((opciones && opciones.lineas) || []).forEach(function (l) {
                var escala = chart.scales[l.eje];
                if (!escala) { return; }
                var p = escala.getPixelForValue(l.valor);
                ctx.save();
                ctx.strokeStyle = GRIS;
                ctx.lineWidth = 1.5;
                ctx.setLineDash([5, 4]);
                ctx.beginPath();
                if (l.eje === 'x') { ctx.moveTo(p, area.top); ctx.lineTo(p, area.bottom); }
                else { ctx.moveTo(area.left, p); ctx.lineTo(area.right, p); }
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.fillStyle = '#5b6474';
                ctx.font = '12px Barlow, system-ui, sans-serif';
                if (l.eje === 'x') { ctx.textAlign = 'left'; ctx.fillText(l.texto, p + 4, area.top + 12); }
                else { ctx.textAlign = 'right'; ctx.fillText(l.texto, area.right, p - 5); }
                ctx.restore();
            });
        }
    };

    function crearGrafica(lienzo, config) {
        if (!window.Chart) {
            mostrarError('No se pudo cargar la biblioteca de gráficas (Chart.js). Revisa la conexión a internet.');
            return;
        }
        window.Chart.defaults.font.family = 'Barlow, system-ui, sans-serif';
        window.Chart.defaults.color = '#5b6474';
        config.plugins = [lineasReferencia];
        grafica = new window.Chart(lienzo, config);
    }

    function barrasHorizontales(lienzo, etiquetas, valores, maximo, lineas, tooltip, unidad) {
        $('modulo-grafica-envoltura').style.height = Math.max(220, etiquetas.length * 34 + 60) + 'px';
        crearGrafica(lienzo, {
            type: 'bar',
            data: { labels: etiquetas, datasets: [{ data: valores, backgroundColor: AZUL, borderRadius: 3, maxBarThickness: 22 }] },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
                plugins: {
                    legend: { display: false },
                    lineasReferencia: { lineas: lineas },
                    tooltip: { callbacks: { label: tooltip } }
                },
                scales: {
                    x: { beginAtZero: true, max: maximo, grid: { color: '#e8ebf0' }, border: { display: false },
                         ticks: { callback: function (v) { return SC.numero(v, 0) + unidad; } } },
                    y: { grid: { display: false } }
                }
            }
        });
    }

    function tabla(titulo, sub, columnas, filas, vacio) {
        $('modulo-tabla-titulo').textContent = titulo;
        $('modulo-tabla-sub').textContent = sub || '';
        var t = $('modulo-tabla');
        var thead = t.querySelector('thead'), tbody = t.querySelector('tbody');
        SC.vaciar(thead);
        SC.vaciar(tbody);
        var tr = SC.el('tr');
        columnas.forEach(function (c) {
            var th = SC.el('th', c.num ? 'num' : null, c.titulo);
            th.setAttribute('scope', 'col');
            tr.appendChild(th);
        });
        thead.appendChild(tr);
        filas.forEach(function (f) {
            var fila = SC.el('tr');
            columnas.forEach(function (c) {
                var td = SC.el('td', c.num ? 'num' : null);
                var v = c.v(f);
                if (v && v.nodeType) { td.appendChild(v); } else { td.textContent = v === null || v === undefined ? '–' : String(v); }
                fila.appendChild(td);
            });
            tbody.appendChild(fila);
        });
        $('modulo-tabla-vacio').textContent = vacio || 'Sin registros.';
        $('modulo-tabla-vacio').hidden = filas.length > 0;
    }

    function pintarCasos(datos) {
        var caja = $('modulo-casos-caja');
        var lista = $('modulo-casos');
        SC.vaciar(lista);
        if (!datos) { caja.hidden = true; return; }
        caja.hidden = false;
        var casos = (datos.recomendaciones || []).slice(0, 5);
        $('modulo-casos-vacio').hidden = casos.length > 0;
        casos.forEach(function (r) {
            var li = SC.el('li', 'caso-modulo');
            var a = SC.el('a', 'caso-enlace');
            a.href = SC.CTX + '/soluciones?id=' + encodeURIComponent(r.recomendacion_id);
            a.appendChild(SC.el('span', 'caso-titulo', SC.ortografia(r.titulo)));
            var lado = SC.el('span', 'caso-lado');
            lado.appendChild(SC.el('span', 'caso-monto', SC.pesos(r.impacto_estimado_mxn)));
            lado.appendChild(SC.insigniaEstado(r.severidad));
            a.appendChild(lado);
            li.appendChild(a);
            lista.appendChild(li);
        });
    }

    /* ------------------------------------------------------------- modulos */

    function pintarCompras(d) {
        encabezado(periodo(d) + ' · tipo de cambio real de Banxico', d);
        var serie = d.tipo_cambio.serie || [];
        var ultima = serie[serie.length - 1];
        var diaria = d.tipo_cambio.diaria;
        var lienzo = seccionGrafica('Tipo de cambio FIX USD/MXN',
            'Dato real de Banxico SIE (serie SF43718); las compras se valúan al FIX de la fecha de cada orden (CC-03, CC-15)',
            (ultima ? 'Último FIX publicado: ' + SC.numero(ultima.tasa, 4) + ' MXN por dólar (' + SC.fecha(ultima.fecha) + ').' : '') +
            (diaria ? ' Tasa diaria de ExchangeRate-API: ' + SC.numero(diaria.tasa, 4) + ' (' + SC.fecha(diaria.fecha) + ').' : ''),
            'Tipo de cambio FIX diario de Banxico, pesos por dólar');
        $('modulo-grafica-envoltura').style.height = '280px';
        crearGrafica(lienzo, {
            type: 'line',
            data: {
                labels: serie.map(function (p) { return SC.fecha(p.fecha); }),
                datasets: [{ label: 'FIX', data: serie.map(function (p) { return p.tasa; }), borderColor: AZUL,
                             borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.15 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: { display: false },
                           tooltip: { callbacks: { label: function (i) { return 'FIX: ' + SC.numero(i.raw, 4) + ' MXN por dólar'; } } } },
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                    y: { grid: { color: '#e8ebf0' }, border: { display: false },
                         ticks: { maxTicksLimit: 5, callback: function (v) { return SC.numero(v, 2); } } }
                }
            }
        });
        tabla('Compras por proveedor', 'Órdenes emitidas en los últimos 30 días · montos en MXN al FIX de cada orden · total ' + SC.pesos(d.compras_mxn) + ' MXN', [
            { titulo: 'Proveedor', v: function (p) { return SC.ortografia(p.nombre); } },
            { titulo: 'País', v: function (p) { return SC.ortografia(p.pais); } },
            { titulo: 'Órdenes', num: true, v: function (p) { return SC.numero(p.ordenes, 0); } },
            { titulo: 'En tránsito', num: true, v: function (p) { return SC.numero(p.en_transito, 0); } },
            { titulo: 'Unidades', num: true, v: function (p) { return SC.numero(p.unidades, 0); } },
            { titulo: 'Monto (MXN)', num: true, v: function (p) { return SC.pesos(p.monto_mxn); } },
            { titulo: 'Participación', num: true, v: function (p) { return SC.numero(p.participacion_pct, 1) + ' %'; } },
            { titulo: 'Variación de costo', num: true, v: function (p) { return SC.conSigno(p.variacion_costo_pct, 2) + ' %'; } }
        ], d.proveedores, 'No hubo órdenes en la ventana.');
    }

    function pintarInventarios(d) {
        encabezado(periodo(d) + ' · cobertura con la demanda media de ' + d.ventana_demanda_dias + ' días', d);
        var skus = d.por_sku || [];
        var lienzo = seccionGrafica('Días de cobertura por producto',
            'Stock de la red entre la demanda media diaria; seguridad ' + d.umbral_seguridad_dias + ' días, exceso arriba de ' + d.umbral_exceso_dias + ' días (CC-19)',
            'Los productos con menos días de cobertura van arriba.', 'Días de cobertura por producto contra los umbrales de seguridad y exceso');
        barrasHorizontales(lienzo, skus.map(function (s) { return SC.ortografia(s.producto); }),
            skus.map(function (s) { return s.cobertura_dias || 0; }), undefined,
            [{ eje: 'x', valor: d.umbral_seguridad_dias, texto: 'Seguridad ' + d.umbral_seguridad_dias + ' d' },
             { eje: 'x', valor: d.umbral_exceso_dias, texto: 'Exceso ' + d.umbral_exceso_dias + ' d' }],
            function (i) {
                var s = skus[i.dataIndex];
                return SC.numero(s.cobertura_dias, 1) + ' días · stock ' + SC.numero(s.stock, 0) + ' u · demanda ' +
                    SC.numero(s.demanda_media_diaria, 1) + ' u/día · en tránsito ' + SC.numero(s.en_transito, 0) + ' u';
            }, ' d');
        tabla('Stock y cobertura por almacén', 'Stock al cierre de la fecha de corte · órdenes en tránsito no incluidas en la cobertura', [
            { titulo: 'Almacén', v: function (r) { return corto(r.almacen); } },
            { titulo: 'Producto', v: function (r) { return SC.ortografia(r.producto); } },
            { titulo: 'Stock (u)', num: true, v: function (r) { return SC.numero(r.stock, 0); } },
            { titulo: 'Demanda diaria (u)', num: true, v: function (r) { return SC.numero(r.demanda_media_diaria, 1); } },
            { titulo: 'En tránsito (u)', num: true, v: function (r) { return SC.numero(r.en_transito, 0); } },
            { titulo: 'Cobertura', num: true, v: function (r) { return r.cobertura_dias === null ? '–' : SC.numero(r.cobertura_dias, 1) + ' días'; } },
            { titulo: 'Estado', v: function (r) { var e = COBERTURA[r.estado]; return insignia(e[0], e[1]); } }
        ], d.detalle);
    }

    function pintarLogistica(d) {
        encabezado(periodo(d) + ' · clima real de Open-Meteo', d);
        var rutas = (d.rutas || []).slice().sort(function (a, b) { return a.a_tiempo_pct - b.a_tiempo_pct; });
        var lienzo = seccionGrafica('Entregas a tiempo por ruta',
            'Envíos recibidos en los últimos 30 días, de proveedor a almacén; meta 90 % (CC-16)',
            'Las rutas con menor puntualidad van arriba.', 'Porcentaje de entregas a tiempo por ruta contra la meta de 90 %');
        barrasHorizontales(lienzo, rutas.map(function (r) { return SC.ortografia(r.proveedor) + ' → ' + corto(r.almacen); }),
            rutas.map(function (r) { return r.a_tiempo_pct; }), 100,
            [{ eje: 'x', valor: 90, texto: 'Meta 90 %' }],
            function (i) {
                var r = rutas[i.dataIndex];
                return SC.numero(r.a_tiempo_pct, 1) + ' % a tiempo · ' + r.envios + ' envíos · retraso promedio ' +
                    SC.numero(r.retraso_promedio_dias, 1) + ' días · ' + r.con_clima_severo + ' con lluvia fuerte o tormenta';
            }, ' %');
        tabla('Rutas y clima', 'Envíos en tránsito y últimos recibidos · peor condición de la ruta entre el despacho y el almacén; en tránsito, solo hasta la fecha de corte (CC-04)', [
            { titulo: 'Envío', v: function (e) { return 'ENV-' + String(e.envio_id).padStart(4, '0'); } },
            { titulo: 'Proveedor', v: function (e) { return SC.ortografia(e.proveedor); } },
            { titulo: 'Almacén', v: function (e) { return corto(e.almacen); } },
            { titulo: 'Llegada estimada', v: function (e) { return SC.fecha(e.llegada_estimada); } },
            { titulo: 'Llegada real', v: function (e) { return e.llegada_real ? SC.fecha(e.llegada_real) : '–'; } },
            { titulo: 'Estado', v: function (e) {
                var x = ENVIO[e.estado] || [e.estado, 'estado-neutro'];
                return insignia(e.dias_tarde ? x[0] + ' ' + e.dias_tarde + (e.dias_tarde === 1 ? ' día' : ' días') : x[0], x[1]);
            } },
            { titulo: 'Clima en ruta', v: function (e) {
                if (!e.condicion_climatica) { return 'Sin dato aún'; }
                return (CLIMA[e.condicion_climatica] || '–') + ' · ' + SC.numero(e.precipitacion_mm, 1) + ' mm' +
                    (e.clima_parcial ? ' (hasta el corte)' : '');
            } },            { titulo: 'Flete (MXN)', num: true, v: function (e) { return SC.pesos(e.costo_flete_mxn); } }
        ], d.envios);
    }

    function estadoUtilizacion(v) {
        var r = Math.round(v * 10) / 10;                 // CC-23: sobre el valor publicado
        return r <= 85 ? 'EN_META' : r <= 95 ? 'ATENCION' : 'CRITICO';
    }

    function pintarAlmacenes(d) {
        encabezado(periodo(d) + ' · volumen ocupado contra capacidad', d);
        var lista = d.almacenes || [];
        var lienzo = seccionGrafica('Utilización diaria por almacén',
            'Volumen del stock al cierre de cada día entre la capacidad en m³; máximo recomendado ' + SC.numero(d.maximo_pct, 0) + ' % (CC-16)',
            '', 'Utilización diaria de cada almacén contra el máximo de 85 %');
        $('modulo-grafica-envoltura').style.height = '300px';
        var etiquetas = lista.length ? lista[0].serie.map(function (p) { return SC.fecha(p.fecha, false); }) : [];
        crearGrafica(lienzo, {
            type: 'line',
            data: {
                labels: etiquetas,
                datasets: lista.map(function (a, i) {
                    return { label: corto(a.nombre), data: a.serie.map(function (p) { return p.utilizacion_pct; }),
                             borderColor: SERIES[i % SERIES.length], borderDash: i === 2 ? [6, 3] : [], borderWidth: 2,
                             pointRadius: 0, pointHoverRadius: 4, tension: 0.2, fill: false };
                })
            },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 18, boxHeight: 2 } },
                    lineasReferencia: { lineas: [{ eje: 'y', valor: d.maximo_pct, texto: 'Máximo ' + SC.numero(d.maximo_pct, 0) + ' %' }] },
                    tooltip: { callbacks: { label: function (i) { return i.dataset.label + ': ' + SC.numero(i.raw, 1) + ' %'; } } }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                    y: { beginAtZero: true, max: 100, grid: { color: '#e8ebf0' }, border: { display: false },
                         ticks: { maxTicksLimit: 6, callback: function (v) { return SC.numero(v, 0) + ' %'; } } }
                }
            }
        });
        tabla('Capacidad y movimientos', 'Utilización al corte y en los últimos 30 días · unidades que entraron y salieron', [
            { titulo: 'Almacén', v: function (a) { return SC.ortografia(a.nombre); } },
            { titulo: 'Capacidad (m³)', num: true, v: function (a) { return SC.numero(a.capacidad_m3, 0); } },
            { titulo: 'Al corte', num: true, v: function (a) { return SC.numero(a.utilizacion_al_corte_pct, 1) + ' %'; } },
            { titulo: 'Promedio 30 días', num: true, v: function (a) { return SC.numero(a.utilizacion_promedio_pct, 1) + ' %'; } },
            { titulo: 'Máxima 30 días', num: true, v: function (a) { return SC.numero(a.utilizacion_maxima_pct, 1) + ' %'; } },
            { titulo: 'Entradas (u)', num: true, v: function (a) { return SC.numero(a.entradas_unidades, 0); } },
            { titulo: 'Salidas (u)', num: true, v: function (a) { return SC.numero(a.salidas_unidades, 0); } },
            { titulo: 'Estado al corte', v: function (a) { return SC.insigniaEstado(estadoUtilizacion(a.utilizacion_al_corte_pct)); } }
        ], lista);
    }

    function pintarProveedores(d) {
        encabezado('Ventana de ' + d.ventana_dias + ' días al ' + SC.fecha(d.fecha_corte) + ' (fecha de corte) · índice de la red ' +
            SC.numero(d.indice_red, 1) + ' (hace 30 días ' + SC.numero(d.indice_red_hace_30_dias, 1) + ')', d);
        var lista = d.proveedores || [];
        var lienzo = seccionGrafica('Índice de riesgo por proveedor',
            'Score de 0 a 100: retrasos 45 %, cumplimiento 30 % y concentración 25 %; medio desde 40, alto arriba de 60 (CC-07, CC-16)',
            'Pasa el cursor sobre una barra para ver de dónde sale su score.', 'Índice de riesgo de cada proveedor contra los cortes 40 y 60');
        barrasHorizontales(lienzo, lista.map(function (p) { return SC.ortografia(p.nombre); }),
            lista.map(function (p) { return p.score; }), 100,
            [{ eje: 'x', valor: 40, texto: 'Medio 40' }, { eje: 'x', valor: 60, texto: 'Alto 60' }],
            function (i) {
                var p = lista[i.dataIndex], c = p.componentes || {};
                return 'Score ' + SC.numero(p.score, 1) + ' = retrasos ' + SC.numero((c.retrasos || {}).aporte, 1) +
                    ' + cumplimiento ' + SC.numero((c.cumplimiento || {}).aporte, 1) +
                    ' + concentración ' + SC.numero((c.concentracion || {}).aporte, 1);
            }, '');
        tabla('Desempeño por proveedor', 'Componentes del índice en la ventana de ' + d.ventana_dias + ' días', [
            { titulo: 'Proveedor', v: function (p) { return SC.ortografia(p.nombre); } },
            { titulo: 'País', v: function (p) { return SC.ortografia(p.pais); } },
            { titulo: 'Score', num: true, v: function (p) { return SC.numero(p.score, 1); } },
            { titulo: 'Nivel', v: function (p) { var n = NIVEL[p.nivel] || [p.nivel, 'estado-neutro']; return insignia(n[0], n[1]); } },
            { titulo: 'Cambio 30 días', num: true, v: function (p) { return SC.conSigno(p.variacion, 1); } },
            { titulo: 'Entregas a tiempo', num: true, v: function (p) { return SC.numero(((p.componentes || {}).retrasos || {}).entregas_a_tiempo_pct, 1) + ' %'; } },
            { titulo: 'Fill rate', num: true, v: function (p) { return SC.numero(((p.componentes || {}).cumplimiento || {}).fill_rate_proveedor_pct, 1) + ' %'; } },
            { titulo: 'Participación', num: true, v: function (p) { return SC.numero(p.participacion_compras_pct, 1) + ' %'; } },
            { titulo: 'Envíos', num: true, v: function (p) { return SC.numero(p.envios, 0); } }
        ], lista);
    }

    function pintarAlertas(d) {
        encabezado('Indicadores fuera de meta ahora y alertas del simulador en vivo (Módulo 7 del PDR)', null);
        seccionGrafica(null);
        var eventos = d.eventos || [];
        tabla('Historial de alertas', 'Eventos en atención o críticos, del más reciente al más antiguo · fecha y hora simuladas', [
            { titulo: 'Cuándo', v: function (e) { return SC.fecha(e.fecha_simulada, false) + ' ' + SC.hora(e.ocurrido); } },
            { titulo: 'Severidad', v: function (e) { var s = SEVERIDAD[e.severidad]; return insignia(s[0], s[1]); } },
            { titulo: 'Módulo', v: function (e) { return MODULOS[e.modulo] || e.modulo; } },
            { titulo: 'Alerta', v: function (e) { return SC.ortografia(e.titulo); } }
        ], eventos, 'Sin alertas: el simulador no ha publicado eventos en atención o críticos.');
    }

    function pintarUsuarios(d) {
        encabezado('Usuarios del dashboard y su rol (CC-20) · solo lectura', null);
        $('modulo-origen').textContent = 'Datos del sistema';
        seccionGrafica(null);
        var ROLES = { EJECUTIVO: 'Ejecutivo', OPERACIONES: 'Operaciones', ADMIN: 'Administración' };        tabla('Usuarios', SC.ortografia(d.aviso), [
            { titulo: 'Usuario', v: function (u) { return u.usuario; } },
            { titulo: 'Nombre', v: function (u) { return SC.ortografia(u.nombre); } },
            { titulo: 'Rol', v: function (u) { return ROLES[u.rol] || u.rol; } },
            { titulo: 'Estado', v: function (u) { return u.activo ? insignia('Activo', 'estado-ok') : insignia('Inactivo', 'estado-neutro'); } },
            { titulo: 'Último acceso', v: function (u) { return u.ultimo_acceso ? SC.fecha(u.ultimo_acceso) + ' ' + SC.hora(u.ultimo_acceso) : 'Nunca'; } },
            { titulo: 'Intentos fallidos', num: true, v: function (u) { return SC.numero(u.intentos_fallidos || 0, 0); } }
        ], d.usuarios || []);
    }

    var CONFIG = {
        compras: { kpis: ['lead_time', 'variacion_costo', 'impacto_tc'], detalle: '/modulos/compras', casos: 'COMPRAS', pintar: pintarCompras },
        inventarios: { kpis: ['fill_rate', 'rotacion', 'doh'], detalle: '/modulos/inventarios', casos: 'INVENTARIOS', pintar: pintarInventarios },
        logistica: { kpis: ['otif', 'entregas_a_tiempo', 'costo_transporte_unidad'], detalle: '/modulos/logistica', casos: 'LOGISTICA', pintar: pintarLogistica },
        almacenes: { kpis: ['utilizacion'], detalle: '/modulos/almacenes', casos: 'ALMACENES', pintar: pintarAlmacenes },
        proveedores: { kpis: ['riesgo_proveedores', 'otif'], detalle: '/proveedores/riesgo', casos: 'PROVEEDORES', pintar: pintarProveedores },
        alertas: { kpis: 'fuera_de_meta', detalle: '/actividad?solo_alertas=true&limite=100', casos: null, pintar: pintarAlertas },
        administracion: { kpis: null, detalle: '/admin/usuarios', casos: null, pintar: pintarUsuarios }
    };

    /* ----------------------------------------------------------------- carga */

    function indicadores(cfg) {
        if (!cfg.kpis) { return Promise.resolve(null); }
        return Promise.all([SC.api('/kpis'), SC.api('/estaciones')]).then(function (r) {
            var todos = {};
            r[0].kpis.forEach(function (k) { todos[k.clave] = k; });
            r[1].estaciones.forEach(function (e) {
                if (!todos[e.kpi]) {
                    todos[e.kpi] = { clave: e.kpi, nombre: e.kpi === 'entregas_a_tiempo' ? 'Entregas a tiempo' : e.etiqueta,
                                     valor: e.valor, unidad: e.unidad, meta: e.meta, umbral_critico: e.umbral_critico,
                                     sentido: e.sentido, estado: e.estado, origen: 'SIMULADO' };
                }
            });
            if (cfg.kpis === 'fuera_de_meta') {
                return Object.keys(todos).map(function (c) { return todos[c]; })
                    .filter(function (k) { return k.estado === 'ATENCION' || k.estado === 'CRITICO'; })
                    .sort(function (a, b) { return (b.estado === 'CRITICO') - (a.estado === 'CRITICO'); });
            }
            return cfg.kpis.map(function (c) { return todos[c]; }).filter(Boolean);
        });
    }

    function mostrarError(mensaje) {
        var aviso = $('modulo-error');
        aviso.textContent = mensaje;
        aviso.hidden = !mensaje;
    }

    function cargar() {
        var cfg = CONFIG[MODULO];
        if (!cfg) { mostrarError('Módulo desconocido.'); return Promise.resolve(); }
        mostrarError('');
        return Promise.all([
            indicadores(cfg).then(pintarKpis),
            SC.api(cfg.detalle).then(cfg.pintar),
            cfg.casos ? SC.api('/recomendaciones?vista=abiertas&modulo=' + cfg.casos).then(pintarCasos) : Promise.resolve(pintarCasos(null))
        ]).catch(function (err) {
            if (err && err.estado !== 401) { mostrarError(err.message || 'No se pudieron cargar los datos.'); }
        });
    }

    cargar();
    if (MODULO !== 'administracion') {
        setInterval(function () { if (!document.hidden) { cargar(); } }, REFRESCO_MS);
    }
}());