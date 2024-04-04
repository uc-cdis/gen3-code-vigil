var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", ({ value: true }));
const core = __importStar(__nccwpck_require__(2186));
const github = __importStar(__nccwpck_require__(5438));
function run() {
    return __awaiter(this, void 0, void 0, function* () {
        console.log(`starting process for ${github.context.repo.owner}/${github.context.repo.repo}`);
        try {
            const token = core.getInput('github_token');
            const userName = core.getInput('delete_user_name');
            const bodyRegex = core.getInput('body_regex');
            const issueNumber = parseInt(core.getInput('issue_number'));
            const octokit = github.getOctokit(token);
            const deleteComments = (issue) => __awaiter(this, void 0, void 0, function* () {
                var _a;
                const resp = yield octokit.issues.listComments({
                    owner: github.context.repo.owner,
                    repo: github.context.repo.repo,
                    issue_number: issue
                });
                const comments = resp.data.filter(it => { var _a, _b; return ((_a = it.user) === null || _a === void 0 ? void 0 : _a.login) === userName && ((_b = it.body) === null || _b === void 0 ? void 0 : _b.match(bodyRegex)); });
                for (const comment of comments) {
                    console.log(`Processing issue ${comment.issue_url} user: ${(_a = comment.user) === null || _a === void 0 ? void 0 : _a.login} comment: ${comment.body}`);
                    yield octokit.request('DELETE /repos/{owner}/{repo}/issues/comments/{comment_id}', {
                        owner: github.context.repo.owner,
                        repo: github.context.repo.repo,
                        comment_id: comment.id
                    });
                }
            });
            yield deleteComments(issueNumber);
        }
        catch (error) {
            console.error(error);
            console.error(error.stack);
            core.setFailed(error.message);
        }
    });
}
run();
