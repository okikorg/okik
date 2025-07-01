import { Command } from 'commander';
import { spawnSync } from 'child_process';
import Table from 'cli-table3';
import { color } from '../utils/ui';

interface RoutesOptions {
  entryPoint: string;
}

export const routesCommand = new Command('routes')
  .description('Display routes defined in the FastAPI entry point.')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.py')
  .action((opts: RoutesOptions) => {
    const script = `import importlib.util, json, sys, os, traceback
entry_point = sys.argv[1]
module_name = os.path.splitext(os.path.basename(entry_point))[0]
spec = importlib.util.spec_from_file_location(module_name, entry_point)
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
app = getattr(module, 'app', None)
if app is None:
    print(json.dumps({"error": "No 'app' instance found."}))
    sys.exit(1)
from fastapi.routing import APIRoute
routes = []
for route in app.routes:
    if isinstance(route, APIRoute):
        routes.append({"path": route.path, "methods": list(route.methods)})
print(json.dumps(routes))`;

    const result = spawnSync('python', ['-c', script, opts.entryPoint], {
      encoding: 'utf8',
    });

    if (result.error) {
      console.error(color.error(`Failed to run python: ${result.error.message}`));
      return;
    }

    try {
      const data = JSON.parse(result.stdout.trim());
      if (Array.isArray(data)) {
        if (data.length === 0) {
          console.log(color.warning('No routes found.'));
          return;
        }
        const table = new Table({ head: ['Path', 'Methods'] });
        data.forEach((r: any) => table.push([r.path, r.methods.join(', ')]));
        console.log(table.toString());
      } else if (data.error) {
        console.error(color.error(data.error));
      }
    } catch (err) {
      console.error(color.error('Failed to parse routes information.'));
      if (result.stdout) console.error(result.stdout);
      if (result.stderr) console.error(result.stderr);
    }
  });