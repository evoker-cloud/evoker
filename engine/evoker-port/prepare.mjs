import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {chmodSync,cpSync,existsSync,readFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=dirname(fileURLToPath(import.meta.url)),manifest=JSON.parse(readFileSync(resolve(root,'source.json'),'utf8'));
const target=process.argv[2]&&resolve(process.argv[2]);
if(!target||existsSync(target))throw Error('Usage: node integrations/artex/prepare.mjs <new-empty-directory>');
for(const [path,digest] of Object.entries(manifest.files))if(createHash('sha256').update(readFileSync(resolve(root,path))).digest('hex')!==digest)throw Error('Source artifact changed: '+path);
const command=(args,options={})=>execFileSync(args[0],args.slice(1),{stdio:'inherit',...options});
command(['git','clone','--no-checkout',manifest.repository,target]);
command(['git','checkout','--detach',manifest.revision],{cwd:target});
const rev=execFileSync('git',['rev-parse','HEAD'],{cwd:target,encoding:'utf8'}).trim();if(rev!==manifest.revision)throw Error('Unexpected source revision');
command(['go','mod','download','github.com/Autumn-27/norma@'+manifest.norma],{cwd:target});
const module=JSON.parse(execFileSync('go',['mod','download','-json','github.com/Autumn-27/norma@'+manifest.norma],{cwd:target,encoding:'utf8'}));
cpSync(module.Dir,resolve(target,'evoker-norma'),{recursive:true});
// Go's module cache is read-only. Only make the private copy writable.
chmodSync(resolve(target,'evoker-norma/compaction/compaction.go'),0o644);
command(['git','apply',resolve(root,'patches/hosted.patch')],{cwd:target});
command(['patch','-p1','-i',resolve(root,'patches/norma-small-context.patch')],{cwd:resolve(target,'evoker-norma')});
cpSync(resolve(root,'overlay'),target,{recursive:true});
// Build only. This script never starts ARTEX, launches a GPU, or runs a test.
command(['go','build','-p','2','-o',resolve(target,'evoker-artex'),'./cmd/evoker'],{cwd:target});
console.log('Built pinned ARTEX port. Runtime qualification is still required before enabling admissions.');
