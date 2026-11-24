// Extrae la lógica de precio REAL de tienda/assets/app.js y calcula el precio de venta
// de todo el catálogo. Se usa para comparar contra bot/api/server.py.
import fs from 'node:fs';
import path from 'node:path';

const root = process.argv[2] || process.cwd();

function leer(rel) {
  return fs.readFileSync(path.join(root, rel), 'utf8');
}

// --- 1. CONFIG real ---
const window = {};
new Function('window', leer('tienda/assets/config.js'))(window);
const CONFIG = window.TIENDA_CONFIG;
if (!CONFIG) throw new Error('no se pudo leer TIENDA_CONFIG');

// --- 2. Extraer las funciones de precio del app.js ---
const app = leer('tienda/assets/app.js');

function extraerFuncion(nombre) {
  const marca = `const ${nombre} = `;
  const inicio = app.indexOf(marca);
  if (inicio < 0) throw new Error(`no encontré '${nombre}' en app.js`);
  // Recorrer hasta cerrar el bloque de la arrow function.
  let i = app.indexOf('{', inicio);
  if (i < 0) throw new Error(`no encontré el cuerpo de '${nombre}'`);
  let profundidad = 0;
  for (; i < app.length; i++) {
    if (app[i] === '{') profundidad++;
    else if (app[i] === '}') {
      profundidad--;
      if (profundidad === 0) {
        // incluir el ';' final si está
        i++;
        while (app[i] === ';' || app[i] === '\n') {
          if (app[i] === ';') { i++; break; }
          i++;
        }
        return app.slice(inicio, i);
      }
    }
  }
  throw new Error(`no pude cerrar '${nombre}'`);
}

const fuente = [
  extraerFuncion('redondearVenta'),
  extraerFuncion('aplicarRecargo'),
  'return aplicarRecargo;',
].join('\n');

const aplicarRecargo = new Function('CONFIG', fuente)(CONFIG);

// --- 3. Calcular para todo el catálogo ---
const salida = { config: CONFIG, precios: {} };

for (const rel of ['tienda/data/v/todos.json', 'tienda/data/motos/v/todos.json']) {
  const items = JSON.parse(leer(rel));
  for (const p of items) {
    const id = String(p.i || '').trim();
    if (!id) continue;
    salida.precios[id] = {
      p: p.p === undefined ? null : p.p,
      o: p.o === undefined ? null : p.o,
      precio: aplicarRecargo(p.p),
      precio_lista: aplicarRecargo(p.o),
    };
  }
}

const destino = process.argv[3];
const texto = JSON.stringify(salida);
if (destino) {
  fs.writeFileSync(destino, texto, 'utf8');
} else {
  process.stdout.write(texto);
}
