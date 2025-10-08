@{
    ViewBag.Title = "Login";
}

<h2>Sign in</h2>

@if (!string.IsNullOrEmpty(ViewBag.Message as string))
{
    <div class="error">@Html.Raw(ViewBag.Message)</div>
}

@using (Html.BeginForm("Authenticate", "Account", FormMethod.Post)) 
{
    <label for="username">Username</label>
    @Html.TextBox("username", null, new { @class = "form-control", autocomplete = "username", required = "required" })

    <label for="password">Password</label>
    @Html.Password("password", null, new { @class = "form-control", autocomplete = "current-password", required = "required" })

    <button type="submit" class="btn btn-primary">Login</button>
}



body {
    font-family: Arial, sans-serif;
    background: #f7f7f7;
    padding: 40px;
}

.card {
    background: #fff;
    padding: 20px;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    width: 320px;
    margin: 0 auto;
}

input {
    width: 100%;
    padding: 8px;
    margin: 6px 0;
    border: 1px solid #ccc;
    border-radius: 4px;
}

button {
    padding: 10px 14px;
    border: none;
    background: #007bff;
    color: #fff;
    border-radius: 4px;
    cursor: pointer;
}

.error {
    color: #a00;
    margin-bottom: 10px;
}

/*Bootstrap classes added for better styling*/
.form-control{
    width: 100%;
    padding: 8px;
    margin: 6px 0;
    border: 1px solid #ccc;
    border-radius: 4px;
}
.btn{
    padding: 10px 14px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
.btn-primary{
    background: #007bff;
    color: #fff;
}