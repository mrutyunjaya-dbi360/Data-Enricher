import { post, setTokens, setUser } from "../api.js";
import { toast } from "../router.js";

export async function renderLogin(root) {
  root.innerHTML = `
    <div class="login-wrap">
      <article>
        <header><h1>ScrapeOps</h1><p>Sign in with your work email</p></header>
        <form id="login-form">
          <label>Email <input type="email" name="email" required autocomplete="username" /></label>
          <label>Password <input type="password" name="password" required autocomplete="current-password" /></label>
          <button type="submit">Sign in</button>
          <p id="login-err" style="color:#b91c1c" hidden></p>
        </form>
      </article>
    </div>`;
  document.getElementById("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = e.target.querySelector("button");
    btn.classList.add("pending");
    btn.textContent = "Signing in…";
    try {
      const data = await post("/auth/login", {
        email: fd.get("email"),
        password: fd.get("password"),
      });
      setTokens(data.access, data.refresh);
      setUser(data.user);
      location.hash = "#/report";
      location.reload();
    } catch (err) {
      const el = document.getElementById("login-err");
      el.hidden = false;
      el.textContent = err.message;
    } finally {
      btn.classList.remove("pending");
      btn.textContent = "Sign in";
    }
  };
}
