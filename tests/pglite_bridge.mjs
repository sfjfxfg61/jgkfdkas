// Optional local PostgreSQL-in-WASM transport for environments without a server.
import { createInterface } from 'node:readline';
const { PGlite } = await import(process.env.PGLITE_MODULE_PATH || '@electric-sql/pglite');
const db = new PGlite();
await db.waitReady;
const rl=createInterface({input:process.stdin});
for await (const line of rl) {
  try {
    const {sql,params}=JSON.parse(line);
    const results=params ? [await db.query(sql,params)] : await db.exec(sql);
    const result=results.at(-1)||{rows:[],fields:[]};
    process.stdout.write(JSON.stringify({ok:true,...result})+'\n');
  } catch(e) {
    process.stdout.write(JSON.stringify({ok:false,error:e.message})+'\n');
  }
}
await db.close();
