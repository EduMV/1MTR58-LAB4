# Laboratorio EEG - 1MTR58

Repositorio para el Laboratorio 4 de EEG del curso **Fundamentos y Aplicaciones de Biomecatrónica - 1MTR58**.

Adquisición de EEG con BITalino y análisis de carga cognitiva basado en tareas auditivas N-back.

## Archivos

- `nback_audio.py`
  - Ejecuta el test auditivo.

- `Bloque1_EEG_2026_2.ipynb`
  - Introducción al procesamiento de una señal EEG individual.

- `Bloque2_EEG_2026_2.ipynb`
  - Código de referencia para procesar el dataset completo.

- `data_example/`
  - Contiene una señal EEG de ejemplo para trabajar el Bloque 1 antes de realizar la adquisición propia.

## Flujo

1. Ejecutar `nback_audio.py` durante la adquisición con BITalino.
2. Utilizar `Bloque1_EEG_2026_2.ipynb` con la señal de ejemplo.
3. Reutilizar el procesamiento desarrollado en el Bloque 1 con las señales adquiridas.
4. Utilizar `Bloque2_EEG_2026_2.ipynb` como guía para construir el dataset y realizar el análisis de Machine Learning.
5. Interpretar los resultados obtenidos en el reporte del laboratorio.

## Requisitos

Para `nback_audio.py`:

- Python 3.12

Para los notebooks:

Se recomienda utilizar Python 3.12 en Colab con las siguientes librerías:

```bash
pip install numpy pandas matplotlib scipy scikit-learn