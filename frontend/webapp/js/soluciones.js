/*
 * Centro de soluciones (Modulo 6; diseno CC-10; supuestos CC-19).
 *
 * Lee /api/recomendaciones?vista= y /api/recomendaciones/{id} (ApiLecturaServlet) y
 * registra decisiones en /api/decisiones/... (DecisionServlet, rol y CSRF, CC-20).
 * La IA solo recomienda; aprobar, descartar con motivo y cerrar con ahorro real lo
 * hace una persona. Todo se inserta con textContent (prevencion de XSS).
 */
(function () {
    'use strict';

    var SC = window.SC;
    var AZUL_DATO = '#1A56A8';
    var AZUL_CLARO = '#9db7dc';
    var GRIS_META = '#8a94a6';
    var PUEDE_DECIDIR = SC.ROL === 'EJECUTIVO';
    var PUEDE_MARCAR = SC.ROL === 'EJECUTIVO' || SC.ROL === 'OPERACIONES';

    var estado = { vista: 'abiertas', lista: [], id: null, detalle: null, opcion: null, grafica: null };

    function $(id) { return document.getElementById(id); }

    /* ---------------------------------------------------------------- textos */

    var REGLAS = {
        ALZA_PRECIO: 'Alza de precio',
        QUIEBRE_PROYECTADO: 'Quiebre proyectado',
        EXCESO_INVENTARIO: 'Exceso de inventario',
        RETRASO_PROVEEDOR: 'Retrasos de proveedor',
        RETRASOS_PROVEEDOR: 'Retrasos de proveedor',
        CLIMA_RUTA: 'Clima en ruta',
        CONCENTRACION_GASTO: 'Concentración de gasto'
    };
    var MODULOS = {
        COMPRAS: 'Compras', INVENTARIOS: 'Inventarios', LOGISTICA: 'Logística',
        ALMACENES: 'Almacenes', PROVEEDORES: 'Proveedores'
    };
    var ESTADOS_REC = {
        NUEVA: 'Abierta', EN_REVISION: 'En curso', ATENDIDA: 'Atendida', DESCARTADA: 'Descartada'
    };
    var ACCIONES = { APROBAR: 'Aprobó', DESCARTAR: 'Descartó', CERRAR: 'Cerró' };

    function humanizar(clave) {
        if (!clave) { return ''; }
        var t = String(clave).toLowerCase().replace(/_/g, ' ');
        return SC.ortografia(t.charAt(0).toUpperCase() + t.slice(1));
    }

    function vistaDeEstado(e) {
        if (e === 'NUEVA') { return 'abiertas'; }
        if (e === 'EN_REVISION') { return 'en_curso'; }
        return 'resueltas';
    }

    function fechaHora(iso) {
        if (!iso) { return '–'; }
        var h = SC.hora(iso);
        return SC.fecha(iso) + (h ? ' ' + h : '');
    }

    /* --------------------------------------------------------- indicadores */

    function pintarResumen(datos) {
        var r = datos.resumen || {};
        $('ind-abiertas').textContent = SC.numero(r.abiertas, 0);
        $('ind-criticas').textContent = SC.numero(r.criticas, 0) + (r.criticas === 1 ? ' crítica' : ' críticas');
        $('ind-impacto').textContent = SC.pesos(r.impacto_en_juego_mxn);
        $('ind-ahorro').textContent = SC.pesos(r.ahorro_real_90d_mxn);
        $('ind-ahorro-sub').textContent = r.cumplimiento_ahorro_pct === null || r.cumplimiento_ahorro_pct === undefined
            ? (r.ahorro_real_90d_mxn > 0 ? 'Proyectado: ' + SC.pesos(r.ahorro_proyectado_90d_mxn) : 'Aún no hay recomendaciones cerradas')
            : SC.numero(r.cumplimiento_ahorro_pct, 0) + ' % de lo proyectado (' + SC.pesos(r.ahorro_proyectado_90d_mxn) + ')';
        $('ind-tiempo').textContent = r.tiempo_decision_dias === null || r.tiempo_decision_dias === undefined
            ? '–' : SC.numero(r.tiempo_decision_dias, 1) + ' días';
        ['abiertas', 'en_curso', 'resueltas'].forEach(function (v) {
            $('n-' + v).textContent = r[v] === undefined ? '' : String(r[v]);
        });
        $('sol-corte').textContent = 'Fecha de corte: ' + SC.fecha(datos.fecha_corte);
    }

    /* ---------------------------------------------------------------- lista */

    function marcarPestana(vista) {
        document.querySelectorAll('.pestanas [role="tab"]').forEach(function (b) {
            var activa = b.getAttribute('data-vista') === vista;
            b.setAttribute('aria-selected', activa ? 'true' : 'false');
            b.tabIndex = activa ? 0 : -1;
        });
    }

    function cargarLista(vista) {
        estado.vista = vista;
        marcarPestana(vista);
        return SC.api('/recomendaciones?vista=' + encodeURIComponent(vista)).then(function (datos) {
            pintarResumen(datos);
            estado.lista = datos.recomendaciones || [];
            pintarLista();
            return estado.lista;
        });
    }

    function pintarLista() {
        var ul = $('sol-lista');
        SC.vaciar(ul);
        var vacio = $('sol-vacio');
        vacio.hidden = estado.lista.length > 0;
        vacio.textContent = {
            abiertas: 'No hay recomendaciones abiertas.',
            en_curso: 'No hay recomendaciones en curso. Al aprobar una opción, la recomendación pasa aquí.',
            resueltas: 'Aún no hay recomendaciones atendidas ni descartadas.'
        }[estado.vista];

        estado.lista.forEach(function (r) {
            var claseSev = (SC.ESTADOS[r.severidad] || SC.ESTADOS.SIN_DATOS).clase;
            var li = SC.el('li', 'sol-item sol-' + claseSev);
            var b = SC.el('button', 'sol-boton');
            b.type = 'button';
            b.setAttribute('aria-pressed', r.recomendacion_id === estado.id ? 'true' : 'false');
            b.addEventListener('click', function () { seleccionar(r.recomendacion_id); });

            var texto = SC.el('span', 'sol-texto');
            texto.appendChild(SC.el('span', 'sol-titulo', SC.ortografia(r.titulo)));
            var contexto = [MODULOS[r.modulo] || humanizar(r.modulo), r.producto, r.proveedor, r.almacen]
                .filter(Boolean).map(SC.ortografia).join(' · ');
            texto.appendChild(SC.el('span', 'sol-sub', contexto));
            b.appendChild(texto);

            var lado = SC.el('span', 'sol-lado');
            if (r.estado === 'ATENDIDA') {
                lado.appendChild(SC.el('span', 'sol-monto', SC.pesos(r.ahorro_real_mxn)));
                lado.appendChild(SC.el('span', 'insignia estado-ok', 'Atendida'));
            } else if (r.estado === 'DESCARTADA') {
                lado.appendChild(SC.el('span', 'sol-monto texto-suave', SC.pesos(r.impacto_estimado_mxn)));
                lado.appendChild(SC.el('span', 'insignia estado-neutro', 'Descartada'));
            } else {
                lado.appendChild(SC.el('span', 'sol-monto', SC.pesos(r.impacto_estimado_mxn)));
                lado.appendChild(SC.insigniaEstado(r.severidad));
            }
            b.appendChild(lado);
            li.appendChild(b);
            ul.appendChild(li);
        });
    }

    /* -------------------------------------------------------------- detalle */

    function seleccionar(id) {
        estado.id = id;
        document.querySelectorAll('.sol-boton').forEach(function (b, i) {
            b.setAttribute('aria-pressed', estado.lista[i] && estado.lista[i].recomendacion_id === id ? 'true' : 'false');
        });
        try { history.replaceState(null, '', SC.CTX + '/soluciones?id=' + encodeURIComponent(id)); } catch (e) { /* sin historial */ }
        return SC.api('/recomendaciones/' + encodeURIComponent(id)).then(pintarDetalle).catch(mostrarError);
    }

    function pintarDetalle(d) {
        estado.detalle = d;
        var ev = d.evidencia || {};
        $('sol-sin-seleccion').hidden = true;
        $('det').hidden = false;
        $('dec-error').hidden = true;
        $('dec-ok').hidden = true;

        $('det-meta').textContent = [MODULOS[d.modulo] || humanizar(d.modulo), REGLAS[d.codigo_regla] || humanizar(d.codigo_regla),
            'detectada el ' + fechaHora(d.fecha_deteccion), ESTADOS_REC[d.estado] || humanizar(d.estado)].join(' · ');
        $('det-titulo').textContent = SC.ortografia(d.titulo);
        $('det-impacto').textContent = SC.pesos(d.impacto_estimado_mxn);
        var sev = $('det-severidad');
        SC.vaciar(sev);
        sev.appendChild(SC.insigniaEstado(d.severidad));
        $('det-descripcion').textContent = SC.ortografia(d.descripcion || d.solucion_recomendada);

        pintarEvidencia(ev);
        pintarOpciones(d);
        $('det-confianza').textContent = 'Confianza del modelo: ' + SC.numero((d.confianza || 0) * 100, 0) +
            ' %. Recomendación: ' + SC.ortografia(d.solucion_recomendada) + '.';
        var razones = $('det-razones');
        SC.vaciar(razones);
        (ev.razones || []).forEach(function (t) { razones.appendChild(SC.el('li', null, SC.ortografia(t))); });
        pintarDatos($('det-supuestos'), ev.supuestos || {}, SUPUESTOS);
        pintarPlan(d);
        pintarResultado(d);
        pintarDecision(d);
        pintarHistorial(ev.historial || []);
    }

    /* ------------------------------------------------------------ evidencia */

    var DATOS = {
        alza_pct: ['Alza de precio', 'pct'],
        precio_base_usd: ['Precio base (mediana de 90 días)', 'usd'],
        precio_actual_usd: ['Precio promedio de 30 días', 'usd'],
        volumen_30_dias: ['Volumen de 30 días', 'u'],
        ordenes_recientes: ['Órdenes recientes', 'entero'],
        score_anomalia_max: ['Score de anomalía máximo (Isolation Forest)', 'dec3'],
        tipo_cambio_fix: ['Tipo de cambio FIX de Banxico (real)', 'dec4'],
        stock_actual: ['Stock actual', 'u'],
        punto_reorden: ['Punto de reorden', 'u'],
        dias_para_quiebre: ['Días para el quiebre', 'entero'],
        valor_unitario_mxn: ['Valor unitario', 'mxn'],
        mape_pronostico_sku: ['MAPE del pronóstico del SKU', 'ratio'],
        unidades_sin_surtir: ['Unidades sin surtir en 14 días', 'u'],
        retraso_esperado_dias: ['Retraso esperado del proveedor', 'dias'],
        demanda_diaria_pronosticada: ['Demanda diaria pronosticada', 'u'],
        variacion_demanda_14_vs_28_dias_pct: ['Demanda de 14 días contra la de 28', 'pctSigno']
    };
    var SUPUESTOS = {
        margen_bruto: ['Margen bruto para valuar la venta perdida', 'ratio'],
        costo_mantener_anual: ['Costo anual de mantener inventario', 'ratio'],
        factor_flete_expres: ['Flete exprés contra el normal', 'veces'],
        horizonte_dias: ['Horizonte de evaluación', 'dias'],
        cobertura_minima_origen_dias: ['Cobertura mínima del almacén que transfiere', 'dias'],
        exceso_cobertura_dias: ['Umbral de exceso de inventario', 'dias'],
        umbral_puntualidad_30d: ['Puntualidad mínima de proveedor (30 días)', 'ratio'],
        umbral_alza_precio: ['Alza de precio relevante', 'ratio'],
        umbral_concentracion: ['Concentración de gasto', 'ratio'],
        prob_exito_negociacion: ['Probabilidad de éxito al negociar', 'ratio'],
        impacto_minimo_mxn: ['Impacto mínimo para abrir un caso', 'mxn'],
        minimo_envios_30d: ['Mínimo de envíos en 30 días', 'entero'],
        dias_manejo_transferencia: ['Días de manejo de una transferencia', 'dias']
    };
    var OMITIR = ['metodo', 'razones', 'supuestos', 'tipo_grafica', 'stock_proyectado_sin_accion',
        'envios_en_transito', 'historial', 'fecha_corte'];

    function formato(valor, tipo) {
        if (valor === null || valor === undefined) { return '–'; }
        if (typeof valor === 'boolean') { return valor ? 'Sí' : 'No'; }
        if (typeof valor !== 'number') { return SC.ortografia(String(valor)); }
        switch (tipo) {
            case 'pct': return SC.numero(valor, 1) + ' %';
            case 'pctSigno': return SC.conSigno(valor, 1) + ' %';
            case 'ratio': return SC.numero(valor * 100, valor * 100 % 1 ? 1 : 0) + ' %';
            case 'usd': return SC.numero(valor, 2) + ' USD';
            case 'mxn': return SC.pesos(valor) + ' MXN';
            case 'u': return SC.numero(valor, valor % 1 ? 1 : 0) + ' u';
            case 'dias': return SC.numero(valor, valor % 1 ? 1 : 0) + (valor === 1 ? ' día' : ' días');
            case 'veces': return SC.numero(valor, 1) + ' veces';
            case 'entero': return SC.numero(valor, 0);
            case 'dec3': return SC.numero(valor, 3);
            case 'dec4': return SC.numero(valor, 4);
            default: return SC.numero(valor, valor % 1 ? 2 : 0);
        }
    }

    function pintarDatos(dl, datos, etiquetas) {
        SC.vaciar(dl);
        Object.keys(datos).forEach(function (k) {
            var v = datos[k];
            if (OMITIR.indexOf(k) >= 0 || (v !== null && typeof v === 'object')) { return; }
            var e = etiquetas[k] || [humanizar(k), null];
            var fila = SC.el('div', 'det-dato');
            fila.appendChild(SC.el('dt', null, e[0]));
            fila.appendChild(SC.el('dd', null, formato(v, e[1])));
            dl.appendChild(fila);
        });
    }

    function nuevaGrafica(config) {
        if (estado.grafica) { estado.grafica.destroy(); estado.grafica = null; }
        if (!window.Chart) { return; }
        window.Chart.defaults.font.family = 'Barlow, system-ui, sans-serif';
        window.Chart.defaults.color = '#5b6474';
        estado.grafica = new window.Chart($('det-grafica'), config);
    }

    function pintarEvidencia(ev) {
        var caja = $('det-grafica-caja');
        var nota = $('det-grafica-nota');
        var lienzo = $('det-grafica');
        pintarDatos($('det-datos'), ev, DATOS);
        $('det-metodo').textContent = SC.ortografia(ev.metodo || '');

        if (ev.tipo_grafica === 'stock_proyectado' && (ev.stock_proyectado_sin_accion || []).length) {
            caja.hidden = false;
            var serie = [{ fecha: ev.fecha_corte, stock: ev.stock_actual }].concat(ev.stock_proyectado_sin_accion);
            var etiquetas = serie.map(function (p) { return SC.fecha(p.fecha, false); });
            lienzo.setAttribute('aria-label', 'Stock proyectado sin actuar durante 14 días contra el punto de reorden');
            nuevaGrafica({
                type: 'line',
                data: {
                    labels: etiquetas,
                    datasets: [
                        { label: 'Stock proyectado sin actuar', data: serie.map(function (p) { return p.stock; }),
                          borderColor: AZUL_DATO, backgroundColor: 'rgba(26, 86, 168, 0.10)', borderWidth: 2,
                          pointRadius: 0, pointHoverRadius: 4, fill: 'origin', tension: 0.2 },
                        { label: 'Punto de reorden', data: serie.map(function () { return ev.punto_reorden; }),
                          borderColor: GRIS_META, borderWidth: 1.5, borderDash: [5, 4], pointRadius: 0, fill: false }
                    ]
                },
                options: opcionesLinea('u')
            });
            var partes = [];
            var quiebre = (ev.stock_proyectado_sin_accion || []).filter(function (p) { return p.stock <= 0; })[0];
            if (quiebre) { partes.push('Sin actuar, el stock se agota el ' + SC.fecha(quiebre.fecha) + '.'); }
            (ev.envios_en_transito || []).forEach(function (e) {
                partes.push('En tránsito: ' + SC.numero(e.unidades, 0) + ' u de ' + SC.ortografia(e.proveedor) +
                    ', llegada estimada ' + SC.fecha(e.llegada_estimada) + ' (a tiempo ' + SC.numero(e.prob_a_tiempo * 100, 0) + ' %).');
            });
            nota.textContent = partes.join(' ');
        } else if (ev.tipo_grafica === 'precio' && ev.precio_base_usd !== undefined) {
            caja.hidden = false;
            lienzo.setAttribute('aria-label', 'Precio base de 90 días contra el precio promedio de 30 días, en USD');
            nuevaGrafica({
                type: 'bar',
                data: {
                    labels: ['Base (mediana de 90 días)', 'Actual (promedio de 30 días)'],
                    datasets: [{ label: 'Precio unitario', data: [ev.precio_base_usd, ev.precio_actual_usd],
                                 backgroundColor: [AZUL_CLARO, AZUL_DATO], borderRadius: 4, maxBarThickness: 64 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { legend: { display: false },
                        tooltip: { callbacks: { label: function (i) { return SC.numero(i.raw, 2) + ' USD'; } } } },
                    scales: {
                        x: { grid: { display: false } },
                                                y: { beginAtZero: true, grid: { color: '#e8ebf0' }, border: { display: false },
                             ticks: { maxTicksLimit: 5, callback: function (v) { return SC.numero(v, 0) + ' USD'; } } }
                    }
                }
            });
            nota.textContent = 'Alza de ' + SC.numero(ev.alza_pct, 1) + ' % sobre la base en ' +
                SC.numero(ev.ordenes_recientes, 0) + ' órdenes recientes; ' + SC.numero(ev.volumen_30_dias, 0) + ' u en 30 días.';
        } else {
            caja.hidden = true;
            if (estado.grafica) { estado.grafica.destroy(); estado.grafica = null; }
            nota.textContent = '';
        }
    }

    function opcionesLinea(unidad) {
        return {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 18, boxHeight: 2 } },
                tooltip: { callbacks: { label: function (i) { return i.dataset.label + ': ' + SC.numero(i.raw, 1) + ' ' + unidad; } } }
            },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                y: { beginAtZero: true, grid: { color: '#e8ebf0' }, border: { display: false },
                     ticks: { maxTicksLimit: 5, callback: function (v) { return SC.numero(v, 0); } } }
            }
        };
    }

    /* ------------------------------------------------------------- opciones */

    function pintarOpciones(d) {
        var ul = $('det-opciones');
        SC.vaciar(ul);
        var opciones = d.opciones || [];
        var max = Math.max.apply(null, opciones.map(function (o) { return o.costo_total_esperado_mxn || 0; }).concat([1]));
        var sinAccion = opciones.filter(function (o) { return o.clave === 'SIN_ACCION'; })[0];
        var elegible = PUEDE_DECIDIR && d.estado === 'NUEVA';
        var preferida = opciones.filter(function (o) { return o.elegida; })[0] || opciones.filter(function (o) { return o.recomendada; })[0];
        estado.opcion = preferida ? preferida.clave : null;

        opciones.forEach(function (o) {
            var li = SC.el('li', 'opcion' + (o.recomendada ? ' opcion-recomendada' : ''));
            var cabeza = SC.el(elegible ? 'label' : 'div', 'opcion-cabeza');
            if (elegible) {
                var radio = SC.el('input');
                radio.type = 'radio';
                radio.name = 'opcion';
                radio.value = o.clave;
                radio.checked = o.clave === estado.opcion;
                radio.addEventListener('change', function () {
                    estado.opcion = o.clave;
                    $('dec-nueva-texto').textContent = textoOpcionElegida();
                });
                cabeza.appendChild(radio);
            }
            var titulo = SC.el('span', 'opcion-titulo', SC.ortografia(o.titulo));
            cabeza.appendChild(titulo);
            if (o.recomendada) { cabeza.appendChild(SC.el('span', 'insignia insignia-ia', 'Recomendada por la IA')); }
            if (o.elegida && d.estado !== 'NUEVA') { cabeza.appendChild(SC.el('span', 'insignia insignia-elegida', 'Elegida')); }
            li.appendChild(cabeza);
            li.appendChild(SC.el('p', 'opcion-detalle', SC.ortografia(o.detalle)));

            var barra = SC.el('div', 'opcion-barra');
            var relleno = SC.el('span', 'opcion-relleno');
            relleno.style.width = Math.max(2, Math.round((o.costo_total_esperado_mxn || 0) / max * 100)) + '%';
            barra.appendChild(relleno);
            li.appendChild(barra);

            var cifras = SC.el('p', 'opcion-cifras');
            cifras.appendChild(SC.el('strong', null, SC.pesos(o.costo_total_esperado_mxn) + ' MXN'));
            cifras.appendChild(document.createTextNode(' costo total esperado'));
            if (o.riesgo_residual !== null && o.riesgo_residual !== undefined) {
                cifras.appendChild(document.createTextNode(' · riesgo residual ' + SC.numero(o.riesgo_residual * 100, 0) + ' %'));
            }
            if (sinAccion && o.clave !== 'SIN_ACCION') {
                cifras.appendChild(document.createTextNode(' · evita ' +
                    SC.pesos(sinAccion.costo_total_esperado_mxn - o.costo_total_esperado_mxn) + ' contra no actuar'));
            }
            li.appendChild(cifras);
            ul.appendChild(li);
        });
    }

    function textoOpcionElegida() {
        var o = (estado.detalle.opciones || []).filter(function (x) { return x.clave === estado.opcion; })[0];
        return o ? 'Opción elegida: ' + SC.ortografia(o.titulo) + '. Al aprobar, la recomendación pasa a En curso.'
                 : 'Elige una opción para aprobar.';
    }

    /* ----------------------------------------------------------------- plan */

    function pasoHecho(p) {
        return !!p.fecha_cierre || /HECH|COMPLET|TERMIN/.test(p.estado || '');
    }

    function pintarPlan(d) {
        var ol = $('det-plan');
        SC.vaciar(ol);
        (d.plan_acciones || []).slice().sort(function (a, b) { return a.orden_paso - b.orden_paso; }).forEach(function (p) {
            var hecho = pasoHecho(p);
            var li = SC.el('li', 'paso' + (hecho ? ' paso-hecho' : ''));
            li.appendChild(SC.el('span', 'paso-numero', hecho ? '✓' : String(p.orden_paso))).setAttribute('aria-hidden', 'true');
            var texto = SC.el('div', 'paso-texto');
            texto.appendChild(SC.el('span', 'paso-descripcion', SC.ortografia(p.descripcion)));
            texto.appendChild(SC.el('span', 'paso-sub', SC.ortografia(p.responsable) + ' · compromiso ' + SC.fecha(p.fecha_compromiso) +
                (hecho && p.fecha_cierre ? ' · hecho el ' + SC.fecha(p.fecha_cierre) : '')));
            li.appendChild(texto);
            var lado = SC.el('div', 'paso-lado');
            if (hecho) {
                lado.appendChild(SC.el('span', 'insignia estado-ok', 'Hecho'));
            } else if (d.estado === 'EN_REVISION' && PUEDE_MARCAR) {
                var b = SC.el('button', 'boton boton-claro boton-chico', 'Marcar como hecho');
                b.type = 'button';
                b.addEventListener('click', function () { marcarPaso(d.recomendacion_id, p.accion_id, b); });
                lado.appendChild(b);
            } else {
                lado.appendChild(SC.el('span', 'insignia estado-neutro', 'Pendiente'));
            }
            li.appendChild(lado);
            ol.appendChild(li);
        });
    }

    /* ------------------------------------------------- resultado e historial */

    function pintarResultado(d) {
        var caja = $('det-resultado-caja');
        var dl = $('det-resultado');
        SC.vaciar(dl);
        if (d.estado !== 'ATENDIDA' && d.estado !== 'DESCARTADA') { caja.hidden = true; return; }
        caja.hidden = false;
        var filas = [];
        if (d.estado === 'ATENDIDA') {
            filas.push(['Ahorro real', SC.pesos(d.ahorro_real_mxn) + ' MXN']);
            filas.push(['Ahorro proyectado', SC.pesos(d.impacto_estimado_mxn) + ' MXN']);
            if (d.impacto_estimado_mxn) {
                filas.push(['Real contra proyectado', SC.numero(d.ahorro_real_mxn / d.impacto_estimado_mxn * 100, 0) + ' %']);
            }
        } else {
            filas.push(['Motivo del descarte', SC.ortografia(d.motivo_descarte || '–')]);
        }
        filas.push(['Fecha de cierre', fechaHora(d.fecha_cierre)]);
        filas.forEach(function (f) {
            var fila = SC.el('div', 'det-dato');
            fila.appendChild(SC.el('dt', null, f[0]));
            fila.appendChild(SC.el('dd', null, f[1]));
            dl.appendChild(fila);
        });
    }

    function pintarHistorial(historial) {
        var caja = $('det-historial-caja');
        var ol = $('det-historial');
        SC.vaciar(ol);
        caja.hidden = !historial.length;
        historial.forEach(function (h) {
            var partes = [fechaHora(h.fecha), (h.usuario || 'usuario') + ' ' + (ACCIONES[h.accion] ? ACCIONES[h.accion].toLowerCase() : humanizar(h.accion).toLowerCase())];
            if (h.opcion) { partes.push('opción ' + humanizar(h.opcion).toLowerCase()); }
            if (h.motivo) { partes.push('motivo: ' + SC.ortografia(h.motivo)); }
            if (h.ahorro_real_mxn !== null && h.ahorro_real_mxn !== undefined) { partes.push('ahorro real ' + SC.pesos(h.ahorro_real_mxn) + ' MXN'); }
            ol.appendChild(SC.el('li', null, partes.join(' · ')));
        });
    }

    /* ------------------------------------------------------------- decisión */

    function pintarDecision(d) {
        var abierta = d.estado === 'NUEVA' || d.estado === 'EN_REVISION';
        $('det-decision').hidden = !abierta;
        $('dec-descarte').hidden = true;
        $('dec-motivo').value = '';
        $('dec-ahorro').value = '';
        if (!abierta) { return; }
        $('dec-sin-permiso').hidden = PUEDE_DECIDIR;
        $('dec-nueva').hidden = !(PUEDE_DECIDIR && d.estado === 'NUEVA');
        $('dec-curso').hidden = !(PUEDE_DECIDIR && d.estado === 'EN_REVISION');
        if (d.estado === 'NUEVA') { $('dec-nueva-texto').textContent = textoOpcionElegida(); }
    }

    function ocupado(si) {
        document.querySelectorAll('#det-decision button, #det-plan button').forEach(function (b) { b.disabled = si; });
    }

    function decidir(cuerpo, mensajeOk) {
        var id = estado.id;
        $('dec-error').hidden = true;
        $('dec-ok').hidden = true;
        ocupado(true);
        return SC.enviar('/decisiones/' + encodeURIComponent(id), cuerpo).then(function () {
            return recargar(id, mensajeOk);
        }).catch(function (err) {
            $('dec-error').textContent = err.message;
            $('dec-error').hidden = false;
        }).then(function () { ocupado(false); });
    }

    function marcarPaso(id, accionId, boton) {
        $('dec-error').hidden = true;
        boton.disabled = true;
        SC.enviar('/decisiones/' + encodeURIComponent(id) + '/acciones/' + encodeURIComponent(accionId) + '/hecha', {})
            .then(function () { return recargar(id, 'Paso del plan marcado como hecho.'); })
            .catch(function (err) {
                boton.disabled = false;
                $('dec-error').textContent = err.message;
                $('dec-error').hidden = false;
                $('det-decision').hidden = false;
            });
    }

    /** Vuelve a leer el detalle, cambia de pestaña si cambió el estado y conserva la selección. */
    function recargar(id, mensajeOk) {
        return SC.api('/recomendaciones/' + encodeURIComponent(id)).then(function (d) {
            return cargarLista(vistaDeEstado(d.estado)).then(function () {
                estado.id = id;
                pintarLista();
                pintarDetalle(d);
                var ok = $('dec-ok');
                ok.textContent = mensajeOk;
                ok.hidden = false;
                $('det-decision').hidden = false;
                ['dec-nueva', 'dec-curso', 'dec-descarte', 'dec-sin-permiso'].forEach(function (x) {
                    if (d.estado !== 'NUEVA' && d.estado !== 'EN_REVISION') { $(x).hidden = true; }
                });
            });
        });
    }

    function enlazarDecisiones() {
        $('btn-aprobar').addEventListener('click', function () {
            if (!estado.opcion) {
                $('dec-error').textContent = 'Elige una opción antes de aprobar.';
                $('dec-error').hidden = false;
                return;
            }
            decidir({ accion: 'APROBAR', opcion: estado.opcion }, 'Opción aprobada. La recomendación está En curso; sigue el plan de acción.');
        });
        function mostrarDescarte() {
            $('dec-descarte').hidden = false;
            $('dec-motivo').focus();
        }
        $('btn-mostrar-descarte').addEventListener('click', mostrarDescarte);
        $('btn-mostrar-descarte-2').addEventListener('click', mostrarDescarte);
        $('btn-cancelar-descarte').addEventListener('click', function () { $('dec-descarte').hidden = true; });
        $('btn-descartar').addEventListener('click', function () {
            var motivo = $('dec-motivo').value.trim();
            if (motivo.length < 5) {
                $('dec-error').textContent = 'Escribe el motivo del descarte (al menos 5 caracteres).';
                $('dec-error').hidden = false;
                return;
            }
            decidir({ accion: 'DESCARTAR', motivo: motivo }, 'Recomendación descartada. El motivo queda en el historial.');
        });
        $('btn-cerrar').addEventListener('click', function () {
            var texto = $('dec-ahorro').value.trim();
            var valor = Number(texto);
            if (texto === '' || !isFinite(valor)) {
                $('dec-error').textContent = 'Escribe el ahorro real medido en MXN.';
                $('dec-error').hidden = false;
                return;
            }
            decidir({ accion: 'CERRAR', ahorro_real_mxn: valor }, 'Recomendación cerrada con el ahorro real registrado.');
        });
    }

    /* ------------------------------------------------------------- pestañas */

    function enlazarPestanas() {
        var pestanas = Array.prototype.slice.call(document.querySelectorAll('.pestanas [role="tab"]'));
        pestanas.forEach(function (b, i) {
            b.addEventListener('click', function () { abrirVista(b.getAttribute('data-vista')); });
            b.addEventListener('keydown', function (e) {
                if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') { return; }
                var siguiente = pestanas[(i + (e.key === 'ArrowRight' ? 1 : pestanas.length - 1)) % pestanas.length];
                siguiente.focus();
                abrirVista(siguiente.getAttribute('data-vista'));
            });
        });
    }

    function abrirVista(vista) {
        cargarLista(vista).then(function (lista) {
            if (lista.length) {
                seleccionar(lista[0].recomendacion_id);
            } else {
                estado.id = null;
                $('det').hidden = true;
                $('sol-sin-seleccion').hidden = false;
            }
        }).catch(mostrarError);
    }

    function mostrarError(err) {
        if (err && err.estado === 401) { return; }
        var aviso = $('sol-error');
        aviso.textContent = (err && err.message) || 'No se pudieron cargar los datos.';
        aviso.hidden = false;
    }

    /* ---------------------------------------------------------------- inicio */

    enlazarPestanas();
    enlazarDecisiones();

    var idInicial = Number(new URLSearchParams(window.location.search).get('id'));
    if (idInicial > 0 && Math.floor(idInicial) === idInicial) {
        SC.api('/recomendaciones/' + idInicial).then(function (d) {
            return cargarLista(vistaDeEstado(d.estado)).then(function () {
                estado.id = idInicial;
                pintarLista();
                pintarDetalle(d);
            });
        }).catch(function () { abrirVista('abiertas'); });
    } else {
        abrirVista('abiertas');
    }
}());