/*
 * Utilidades comunes del dashboard (diseno CC-10; seguridad CC-20 y CC-21).
 *
 * - api(): pide datos a los Servlets de /api/ (mismo origen, cookie de sesion).
 *   Nunca llama a FastAPI directamente.
 * - el(): crea elementos con textContent; los datos nunca se insertan como HTML
 *   (prevencion de XSS, OWASP).
 * - ortografia(): la base guarda texto en ASCII (CC-11); la interfaz lo muestra
 *   con acentos.
 */
(function (global) {
    'use strict';

    var cuerpo = global.document ? global.document.body : null;
    var CTX = cuerpo ? (cuerpo.getAttribute('data-ctx') || '') : '';
    var LOCALE = 'es-MX';

    /* ------------------------------------------------------------ peticiones */

    function ErrorApi(estado, mensaje) {
        this.estado = estado;
        this.message = mensaje;
    }
    ErrorApi.prototype = Object.create(Error.prototype);

    function api(ruta) {
        return global.fetch(CTX + '/api' + ruta, {
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin',
            cache: 'no-store'
        }).then(function (r) {
            if (r.status === 401) {
                global.location.assign(CTX + '/login?expirada=1');
                throw new ErrorApi(401, 'Tu sesión expiró.');
            }
            return r.json().catch(function () { return {}; }).then(function (datos) {
                if (!r.ok) {
                    throw new ErrorApi(r.status, datos.mensaje ||
                        'El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.');
                }
                return datos;
            });
        });
    }

    /* -------------------------------------------------------------- DOM seguro */

    function el(etiqueta, clase, texto) {
        var nodo = global.document.createElement(etiqueta);
        if (clase) { nodo.className = clase; }
        if (texto !== undefined && texto !== null) { nodo.textContent = String(texto); }
        return nodo;
    }

    function vaciar(nodo) {
        while (nodo.firstChild) { nodo.removeChild(nodo.firstChild); }
    }

    /* -------------------------------------------------------------- formatos */

    function numero(valor, decimales) {
        if (valor === null || valor === undefined || isNaN(valor)) { return '–'; }
        var d = decimales === undefined ? 1 : decimales;
        return Number(valor).toLocaleString(LOCALE, { minimumFractionDigits: d, maximumFractionDigits: d });
    }

    function pesos(valor) {
        if (valor === null || valor === undefined || isNaN(valor)) { return '–'; }
        return '$' + Number(valor).toLocaleString(LOCALE, { maximumFractionDigits: 0 });
    }

    function conSigno(valor, decimales) {
        if (valor === null || valor === undefined || isNaN(valor)) { return '–'; }
        var texto = numero(Math.abs(valor), decimales);
        return (valor > 0 ? '+' : valor < 0 ? '−' : '') + texto;
    }

    var MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

    /** "2026-09-30" -> "30 sep 2026" (sin depender de la zona horaria del navegador). */
    function fecha(iso, conAnio) {
        if (!iso) { return '–'; }
        var p = String(iso).slice(0, 10).split('-');
        var texto = Number(p[2]) + ' ' + MESES[Number(p[1]) - 1];
        return conAnio === false ? texto : texto + ' ' + p[0];
    }

    /** "2026-10-13T01:57:37" -> "01:57" */
    function hora(isoFechaHora) {
        if (!isoFechaHora || String(isoFechaHora).length < 16) { return ''; }
        return String(isoFechaHora).slice(11, 16);
    }

    /* ------------------------------------------------------------ ortografia */

    var PALABRAS = {
        'Almacen': 'Almacén', 'almacen': 'almacén',
        'Logistica': 'Logística', 'logistica': 'logística',
        'Variacion': 'Variación', 'variacion': 'variación',
        'Rotacion': 'Rotación', 'rotacion': 'rotación',
        'Utilizacion': 'Utilización', 'utilizacion': 'utilización',
        'Electronica': 'Electrónica', 'electronica': 'electrónica',
        'Bajio': 'Bajío', 'Pronostico': 'Pronóstico', 'pronostico': 'pronóstico',
        'dias': 'días', 'Dias': 'Días', 'expres': 'exprés', 'Expres': 'Exprés',
        'Mexico': 'México', 'Lazaro': 'Lázaro', 'Cardenas': 'Cárdenas',
        'Concentracion': 'Concentración', 'concentracion': 'concentración',
        'Precision': 'Precisión', 'precision': 'precisión'
    };

    function ortografia(texto) {
        if (texto === null || texto === undefined) { return ''; }
        return String(texto).replace(/[A-Za-z]+/g, function (palabra) {
            return Object.prototype.hasOwnProperty.call(PALABRAS, palabra) ? PALABRAS[palabra] : palabra;
        });
    }

    /* ---------------------------------------------------------------- estados */

    var ESTADOS = {
        EN_META: { texto: 'En meta', icono: '✓', clase: 'estado-ok' },
        ATENCION: { texto: 'Atención', icono: '!', clase: 'estado-atencion' },
        CRITICO: { texto: 'Crítico', icono: '✕', clase: 'estado-critico' },
        INFORMATIVO: { texto: 'Informativo', icono: 'i', clase: 'estado-neutro' },
        SIN_DATOS: { texto: 'Sin datos', icono: '–', clase: 'estado-neutro' }
    };

    /** Insignia de estado con texto e icono, no solo color (accesibilidad, CC-10). */
    function insigniaEstado(estado) {
        var e = ESTADOS[estado] || ESTADOS.SIN_DATOS;
        var nodo = el('span', 'insignia ' + e.clase);
        nodo.appendChild(el('span', 'insignia-icono', e.icono)).setAttribute('aria-hidden', 'true');
        nodo.appendChild(global.document.createTextNode(e.texto));
        return nodo;
    }

    function unidadVisible(unidad) {
        if (unidad === 'dias') { return 'días'; }
        if (unidad === 'veces al ano') { return 'veces al año'; }
        return unidad || '';
    }

    global.SC = {
        CTX: CTX,
        api: api,
        el: el,
        vaciar: vaciar,
        numero: numero,
        pesos: pesos,
        conSigno: conSigno,
        fecha: fecha,
        hora: hora,
        ortografia: ortografia,
        insigniaEstado: insigniaEstado,
        unidadVisible: unidadVisible,
        ESTADOS: ESTADOS
    };
}(typeof window !== 'undefined' ? window : globalThis));