# Generic icon: three sliders for bass, treble and balance. No vendor logo.
Add-Type -AssemblyName System.Drawing
$outDir = Join-Path $PSScriptRoot '..\custom_components\monoprice\brand'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
foreach ($size in @(256,512)) {
  $bitmap = [Drawing.Bitmap]::new($size,$size)
  $graphics = [Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.Clear([Drawing.Color]::FromArgb(40,60,90))
  $track = [Drawing.Pen]::new([Drawing.Color]::FromArgb(150,170,200),($size * 0.04))
  $track.StartCap = [Drawing.Drawing2D.LineCap]::Round
  $track.EndCap = [Drawing.Drawing2D.LineCap]::Round
  $knob = [Drawing.SolidBrush]::new([Drawing.Color]::White)
  $top = $size * 0.2; $bottom = $size * 0.8; $radius = $size * 0.075
  $columns = @(0.28, 0.5, 0.72); $levels = @(0.62, 0.36, 0.5)
  for ($i = 0; $i -lt 3; $i++) {
    $x = $size * $columns[$i]
    $graphics.DrawLine($track, $x, $top, $x, $bottom)
    $y = $size * $levels[$i]
    $graphics.FillEllipse($knob, $x - $radius, $y - $radius, 2 * $radius, 2 * $radius)
  }
  $name = if ($size -eq 256) {'icon.png'} else {'icon@2x.png'}
  $bitmap.Save((Join-Path $outDir $name),[Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose(); $bitmap.Dispose(); $track.Dispose(); $knob.Dispose()
}
