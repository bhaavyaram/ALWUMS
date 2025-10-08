<%@ Language=VBScript %>
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Login - Classic ASP</title>
  <style>
    body{font-family: Arial, sans-serif; background:#f7f7f7; padding:40px;}
    .card{background:#fff;padding:20px;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.08);width:320px;margin:0 auto;}
    input{width:100%;padding:8px;margin:6px 0;border:1px solid #ccc;border-radius:4px}
    button{padding:10px 14px;border:none;background:#007bff;color:#fff;border-radius:4px;cursor:pointer}
    .error{color:#a00;margin-bottom:10px}
  </style>
</head>
<body>
  <div class="card">
    <h2>Sign in</h2>

    <!-- Show optional message (like error) -->
    <% If Request.QueryString("msg") <> "" Then %>
      <div class="error"><%= Server.HTMLEncode(Request.QueryString("msg")) %></div>
    <% End If %>

    <form method="post" action="authenticate.asp">
      <label for="username">Username</label>
      <input type="text" id="username" name="username" autocomplete="username" required>

      <label for="password">Password</label>
      <input type="password" id="password" name="password" autocomplete="current-password" required>

      <button type="submit">Login</button>
    </form>
  </div>
</body>
</html>
