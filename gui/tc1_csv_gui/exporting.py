"""
@file exporting.py
@brief PDF export methods.
"""

from __future__ import annotations

from .common import *


class ExportingMixin:
    """
    @brief Mixin that groups pdf export methods.
    """
    def export_pdf(self) -> None:
        """
        @brief Export the current Matplotlib figure to a PDF file selected by the user.
        """
        if not self.channels:
            messagebox.showinfo("Guardar PDF", "Primero cargá algún CSV para poder exportar el gráfico.")
            return

        if self.mode == "bode":
            default_name = "bode_tc1.pdf"
        elif self.xy_mode_var.get():
            default_name = "xy_tc1.pdf"
        elif self.loaded_files:
            default_name = f"{Path(self.loaded_files[0]).stem}_grafico.pdf"
        else:
            default_name = "grafico_tc1.pdf"

        out_path = filedialog.asksaveasfilename(
            title="Guardar gráfico como PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not out_path:
            return

        old_size = tuple(self.fig.get_size_inches())
        try:
            self.fig.set_size_inches(11.0, 8.0 if self.mode == "bode" else 6.8)
            self.update_plot()
            mode_text = {"empty": "Vacío", "time": "Tiempo", "bode": "Bode"}.get(self.mode, self.mode)
            visible = [name for name, ctrl in self.controls.items() if ctrl.enabled.get()]
            footer_parts = [f"Modo: {mode_text}"]
            if self.loaded_files:
                footer_parts.append("Archivos: " + ", ".join(Path(p).name for p in self.loaded_files[:3]))
                if len(self.loaded_files) > 3:
                    footer_parts.append(f"+{len(self.loaded_files)-3} más")
            footer_parts.append(f"Canales visibles: {len(visible)}")
            footer_parts.append(datetime.now().strftime("Exportado: %d/%m/%Y %H:%M"))
            footer = "   |   ".join(footer_parts)
            self.fig.text(0.5, 0.012, footer, ha="center", va="bottom", fontsize=8, color="#555555")
            self.fig.subplots_adjust(bottom=0.10)
            self.fig.savefig(out_path, format="pdf", bbox_inches="tight", facecolor="white", edgecolor="none")
            self.status_var.set(f"PDF guardado: {out_path}")
            messagebox.showinfo("PDF guardado", f"Se guardó el gráfico en:\n{out_path}")
        except Exception as exc:
            messagebox.showerror("Error al guardar PDF", f"No se pudo guardar el PDF.\n\nDetalle: {exc}")
        finally:
            self.fig.set_size_inches(*old_size)
            self.update_plot()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
