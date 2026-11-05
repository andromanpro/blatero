using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Globalization;
using System.Windows.Forms;

namespace Blatero.PortableLauncher
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherForm());
        }
    }

    internal sealed class LauncherForm : Form
    {
        private readonly string root;

        private static string L(string russian, string english)
        {
            return CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "ru" ? russian : english;
        }

        public LauncherForm()
        {
            root = AppDomain.CurrentDomain.BaseDirectory;
            Text = "Blatero";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = true;
            ClientSize = new Size(500, 292);
            BackColor = Color.FromArgb(5, 12, 24);
            ForeColor = Color.White;
            Font = new Font("Segoe UI", 10F, FontStyle.Regular, GraphicsUnit.Point);
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

            var title = new Label
            {
                Text = "Blatero",
                AutoSize = false,
                Left = 32,
                Top = 24,
                Width = 436,
                Height = 38,
                ForeColor = Color.FromArgb(0, 220, 255),
                Font = new Font("Segoe UI Semibold", 22F, FontStyle.Bold, GraphicsUnit.Point)
            };
            Controls.Add(title);

            var subtitle = new Label
            {
                Text = L("Локальный ассистент встреч и технических интервью", "Local workspace for meetings, tasks and knowledge"),
                AutoSize = false,
                Left = 34,
                Top = 66,
                Width = 436,
                Height = 28,
                ForeColor = Color.FromArgb(150, 190, 230)
            };
            Controls.Add(subtitle);

            var start = Button(L("Запустить Blatero", "Start Blatero"), 32, 116);
            start.Click += delegate { StartBlatero(); };
            Controls.Add(start);

            var docs = Button(L("Открыть документацию", "Open help"), 270, 116);
            docs.Click += delegate { OpenDocumentation(); };
            Controls.Add(docs);

            var check = Button(L("Проверить установку", "Check installation"), 32, 174);
            check.Width = 428;
            check.Click += delegate { CheckInstallation(); };
            Controls.Add(check);

            var note = new Label
            {
                Text = L("Данные встреч хранятся в Документы\\Blatero. API-ключи настраиваются на этой машине.", "Meeting data is stored in Documents\\Blatero. Configure your own API keys on this computer."),
                AutoSize = false,
                Left = 34,
                Top = 236,
                Width = 432,
                Height = 42,
                ForeColor = Color.FromArgb(120, 160, 205)
            };
            Controls.Add(note);
        }

        private static Button Button(string text, int left, int top)
        {
            return new Button
            {
                Text = text,
                Left = left,
                Top = top,
                Width = 206,
                Height = 46,
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(9, 34, 58),
                ForeColor = Color.White,
                Font = new Font("Segoe UI Semibold", 10F, FontStyle.Bold, GraphicsUnit.Point)
            };
        }

        private void StartBlatero()
        {
            var script = Path.Combine(root, "app", "start_blatero.cmd");
            if (!File.Exists(script))
            {
                MessageBox.Show(
                    L("Не найден app\\start_blatero.cmd. Распакуйте ZIP целиком и запустите снова.", "app\\start_blatero.cmd is missing. Extract the entire ZIP and try again."),
                    "Blatero",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return;
            }

            try
            {
                var info = new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = "/c \"" + script + "\"",
                    WorkingDirectory = Path.Combine(root, "app"),
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                Process.Start(info);
                Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message, L("Blatero: запуск не удался", "Blatero: failed to start"),
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OpenDocumentation()
        {
            var home = Path.Combine(root, "docs", "wiki", "Home.html");
            var english = Path.Combine(root, "docs", "wiki", "en", "Home.html");
            if (CultureInfo.CurrentUICulture.TwoLetterISOLanguageName != "ru" && File.Exists(english))
                home = english;
            if (!File.Exists(home))
            {
                MessageBox.Show(
                    L("Не найдена docs\\wiki\\Home.html. Распакуйте ZIP целиком.", "The offline help is missing. Extract the entire ZIP."),
                    "Blatero",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return;
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = home,
                UseShellExecute = true
            });
        }

        private void CheckInstallation()
        {
            var app = Path.Combine(root, "app");
            var runtime = Path.Combine(root, "runtime", "python.exe");
            var docs = Path.Combine(root, "docs", "wiki", "Home.html");
            var recordingPolicy = Path.Combine(root, "docs", "legal", "RECORDING_POLICY.md");
            var data = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "Blatero");
            var tokenDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "blatero");
            var report = "";
            var ok = true;
            ok &= CheckFile(ref report, Path.Combine(app, "panel.py"), "app\\panel.py");
            ok &= CheckFile(ref report, Path.Combine(app, "startup.py"), "app\\startup.py");
            ok &= CheckFile(ref report, Path.Combine(app, "start_blatero.cmd"), "app\\start_blatero.cmd");
            ok &= CheckFile(ref report, runtime, "runtime\\python.exe");
            ok &= CheckFile(ref report, docs, "docs\\wiki\\Home.html");
            ok &= CheckFile(ref report, recordingPolicy, "docs\\legal\\RECORDING_POLICY.md");
            ok &= CheckWritable(ref report, data, L("Документы\\Blatero", "Documents\\Blatero"));
            ok &= CheckWritable(ref report, tokenDir, "%LOCALAPPDATA%\\blatero");
            MessageBox.Show(
                report,
                ok ? L("Blatero: установка выглядит исправной", "Blatero: installation check passed") : L("Blatero: нужна проверка", "Blatero: installation needs attention"),
                MessageBoxButtons.OK,
                ok ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
        }

        private static bool CheckFile(ref string report, string path, string label)
        {
            var ok = File.Exists(path);
            report += (ok ? "✓ " : "× ") + label + Environment.NewLine;
            return ok;
        }

        private static bool CheckWritable(ref string report, string path, string label)
        {
            try
            {
                Directory.CreateDirectory(path);
                var probe = Path.Combine(path, ".blatero-launcher-write-" + Guid.NewGuid().ToString("N") + ".tmp");
                using (var output = new FileStream(probe, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                using (var writer = new StreamWriter(output))
                    writer.Write("ok");
                File.Delete(probe);
                report += "✓ " + label + L(" доступен для записи", " is writable") + Environment.NewLine;
                return true;
            }
            catch (Exception ex)
            {
                report += "× " + label + ": " + ex.Message + Environment.NewLine;
                return false;
            }
        }
    }
}
