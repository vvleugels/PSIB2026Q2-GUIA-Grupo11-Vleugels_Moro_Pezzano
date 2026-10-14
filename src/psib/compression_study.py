"""Module 4 experiments. Baselines are pipeline comparisons, not ground truth."""
from copy import deepcopy
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .compression import encode_lossless, decode_lossless, jpeg_roundtrip
from .metrics import psnr, ssim
from .segmentation import segment_methods, morphology_variants
from .temporal import track_video, clean_curve, response_parameters
from .stimulus import detect_stimulus_onset
from . import video_io, roi as R
from .calibration import pixels_per_cm, select_points
from .plotting import show_grid, save_fig


def study_options(cfg):
    """Defaults support older prepared configurations; validate before any work."""
    options = dict(jpeg_qualities=[90, 50, 10, 5], temporal_qualities=[50, 10], save_all_frames=False)
    options.update(cfg.get('module4', {}))
    for key in ('jpeg_qualities', 'temporal_qualities'):
        values = options[key]
        if not isinstance(values, list) or not values or any(type(q) is not int or not 1 <= q <= 100 for q in values):
            raise ValueError(f'module4.{key} must contain JPEG qualities in 1..100')
        if len(set(values)) != len(values): raise ValueError(f'Duplicate qualities in {key}')
    if not {90, 50, 10, 5}.issubset(options['jpeg_qualities']):
        raise ValueError('The assignment requires image JPEG qualities 90, 50, 10, 5')
    if not {50, 10}.issubset(options['temporal_qualities']):
        raise ValueError('The assignment requires temporal JPEG qualities 50, 10')
    if type(options['save_all_frames']) is not bool: raise ValueError('save_all_frames must be boolean')
    return options


def _quality(original, decoded):
    if np.array_equal(original, decoded): return dict(PSNR_dB=np.inf, SSIM=1.0)
    if min(original.shape[:2]) < 7:
        raise ValueError('Compression study requires image dimensions of at least 7 pixels for SSIM')
    return dict(PSNR_dB=psnr(original, decoded), SSIM=ssim(original, decoded))


def compare_diameters(baseline, candidate, scale=None):
    """Paired accepted raw measurements; never hide acceptance changes with smoothing."""
    cols = ['frame_index', 'timestamp_s', 'accepted', 'equivalent_diameter_px']
    merged = baseline[cols].merge(candidate[cols], on='frame_index', suffixes=('_baseline', '_jpeg'),
                                  validate='one_to_one', how='outer')
    if len(baseline) != len(candidate) or len(merged) != len(baseline) or merged[['timestamp_s_baseline', 'timestamp_s_jpeg', 'accepted_baseline', 'accepted_jpeg']].isna().any().any():
        raise ValueError('Temporal passes must have the same frame indices and valid timestamps/acceptance')
    if not np.allclose(merged.timestamp_s_baseline, merged.timestamp_s_jpeg, rtol=0, atol=1e-9):
        raise ValueError('Temporal pass timestamps differ')
    use = merged.accepted_baseline & merged.accepted_jpeg
    use &= np.isfinite(merged.equivalent_diameter_px_baseline) & np.isfinite(merged.equivalent_diameter_px_jpeg)
    error = (merged.loc[use, 'equivalent_diameter_px_jpeg']-merged.loc[use, 'equivalent_diameter_px_baseline']).to_numpy()
    result = dict(n_frames=len(baseline), n_paired=int(use.sum()),
                  n_accepted_baseline=int(baseline.accepted.sum()), n_accepted_jpeg=int(candidate.accepted.sum()),
                  n_rejected_baseline=int((~baseline.accepted).sum()), n_rejected_jpeg=int((~candidate.accepted).sum()),
                  status='compared_unvalidated' if len(error) else 'insufficient_paired_data')
    for unit, factor in [('px', 1)] + ([('mm', 10/scale)] if scale is not None else []):
        result.update({f'bias_{unit}': float(error.mean()*factor) if len(error) else np.nan,
                       f'MAE_{unit}': float(np.mean(abs(error))*factor) if len(error) else np.nan,
                       f'RMSE_{unit}': float(np.sqrt(np.mean(error**2))*factor) if len(error) else np.nan})
    return result


def prepare_study(cfg):
    """Resolve the same manual/interactive setup as preceding notebooks once."""
    options = study_options(cfg)
    video = Path(cfg['video_path'])
    frames = video_io.read_frames_at_times(video, [cfg['frames']['primary_time_s'], cfg['frames']['secondary_time_s']])
    roi = R.get_roi(cfg, frames[0][0])
    tracked = R.tracked_frame_rois(frames, roi, cfg['module3'].get('eye_tracking', {}), video)
    inits = [R.pupil_initialization(cfg, item[0], i) for i, item in enumerate(tracked)]
    scale = None
    cal = cfg['calibration']
    if cal['enabled']:
        image, _, _ = video_io.read_frame_at_time(video, cal['frame_time_s'])
        points = select_points(image, title=f"Select ruler endpoints {cal['distance_cm']} cm apart") if cal['mode'] == 'interactive' else cal['points_xy']
        scale = pixels_per_cm(points, cal['distance_cm'])
    out = cfg['_output_dir'] / 'module4' / video.stem
    out.mkdir(parents=True, exist_ok=True)
    m3 = deepcopy(cfg['module3']); m3['roi_reference_time_s'] = frames[0][1]
    kind = m3['record_type'] or video_io.record_type(video)
    stimulus = m3['stimulus_time_s']
    if stimulus is None:
        scan = video_io.scan_video(video)
        stimulus = detect_stimulus_onset(scan['timestamps_s'], scan['brightness'], kind,
                                        cfg['module0']['brightness_smooth_frames'])['onset_s']
    # No hashing or storing the input video itself; record metadata plus effective settings.
    stat = video.stat()
    manifest = dict(video=str(video), size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns,
                    selected_frames=[dict(frame_index=i, timestamp_s=t) for _, t, i in frames],
                    roi=list(roi), initializations=inits, pixels_per_cm=scale,
                    stimulus_s=stimulus, stimulus_source='manual' if m3['stimulus_time_s'] is not None else 'brightness_estimate',
                    module2=cfg['module2'], module3=m3, module4=options,
                    codec_format='PSIC v1', ratio_definition='raw array nbytes / complete encoded file bytes',
                    interpretation='Differences from uncompressed processing, not anatomical accuracy', status='prepared')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    return dict(cfg=cfg, options=options, video=video, frames=frames, roi=roi, tracked=tracked,
                inits=inits, scale=scale, out=out, m3=m3, kind=kind, stimulus=stimulus)


def selected_frame_study(study):
    """Save complete encoded examples and visual evidence for both selected frames."""
    cfg, out, options = study['cfg'], study['out'], study['options']
    rows = []
    for index, ((full, timestamp, frame_index), (rgb, _), init) in enumerate(zip(study['frames'], study['tracked'], study['inits'])):
        m2 = cfg['module2']
        masks = segment_methods(rgb, **init, clusters=m2['clusters'], snake_iterations=m2['snake_iterations'])
        mask = morphology_variants(masks[m2['method']], m2['morphology_radius'], m2['min_component_size'])['opening_closing_filled']
        images = dict(original_rgb=full, eye_rgb=rgb, segmented_rgb=np.where(mask[..., None], rgb, 0).astype(np.uint8),
                      algorithm_mask=mask.astype(np.uint8)*255)
        for region, image in images.items():
            folder = out/'selected_frames'/f'frame_{frame_index}'/region
            folder.mkdir(parents=True, exist_ok=True)
            decoded_jpeg = []
            for codec in ['huffman', 'rle_horizontal', 'rle_vertical'] + [f'jpeg_q{q}' for q in options['jpeg_qualities']]:
                if codec.startswith('jpeg'):
                    quality = int(codec.split('q')[-1]); encoded, decoded = jpeg_roundtrip(image, quality)
                    filename = folder/(codec+'.jpg'); decoded_jpeg.append(decoded)
                else:
                    quality = None; encoded = encode_lossless(image, codec); decoded = decode_lossless(encoded)
                    if not np.array_equal(image, decoded): raise RuntimeError(f'{codec} round trip failed')
                    filename = folder/(codec+'.psic')
                filename.write_bytes(encoded)
                rows.append(dict(frame_index=frame_index, timestamp_s=timestamp, region=region, codec=codec,
                                 jpeg_quality=quality, raw_bytes=image.nbytes, encoded_bytes=len(encoded),
                                 compression_ratio=image.nbytes/len(encoded), **_quality(image, decoded),
                                 sha256=hashlib.sha256(encoded).hexdigest(), path=str(filename.relative_to(out))))
            labels = ['Original']+[f'JPEG Q={q}' for q in options['jpeg_qualities']]
            fig = show_grid([image]+decoded_jpeg, labels, ncols=len(labels), cell=(3, 3),
                            suptitle=f'{region}, {timestamp:.3f}s; mask is algorithm-generated')
            save_fig(fig, f'm4_frame{index}_{region}', cfg); plt.close(fig)
            if region in ('eye_rgb', 'segmented_rgb', 'algorithm_mask'):
                x, y = init['center_xy']; r = max(8, int(init['radius_px']*1.6))
                left, right = max(0, int(x)-r), min(image.shape[1], int(x)+r+1)
                top, bottom = max(0, int(y)-r), min(image.shape[0], int(y)+r+1)
                zooms = [v[top:bottom, left:right] for v in [image]+decoded_jpeg]
                fig = show_grid(zooms, labels, ncols=len(labels), cell=(3, 3), suptitle=f'{region}: pupil-edge enlargement')
                save_fig(fig, f'm4_frame{index}_{region}_edge', cfg); plt.close(fig)
            diffs = [np.abs(image.astype(float)-v.astype(float)).mean(axis=2) if image.ndim == 3
                     else np.abs(image.astype(float)-v.astype(float)) for v in decoded_jpeg]
            fig = show_grid(diffs, labels[1:], ncols=len(diffs), cell=(3, 3), cmap='magma', vmin=0, vmax=255,
                            suptitle=f'{region}: absolute error (0–255; mean over RGB)')
            save_fig(fig, f'm4_frame{index}_{region}_errors', cfg); plt.close(fig)
        print(f'Compression examples complete: frame {frame_index}, {timestamp:.3f}s', flush=True)
    table = pd.DataFrame(rows); table.to_csv(out/'compression_metrics.csv', index=False)
    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    codec_colors = {name: plt.get_cmap('tab10')(i) for i, name in enumerate(table.codec.unique())}
    for column, (region, group) in enumerate(table.groupby('region', sort=False)):
        for _, row in group.iterrows():
            label = row.codec if row.frame_index == table.frame_index.iloc[0] else None
            for axis, metric in zip(axes[:, column], ['PSNR_dB', 'SSIM']):
                if np.isfinite(row[metric]): axis.scatter(row.compression_ratio, row[metric], label=label, s=22, color=codec_colors[row.codec], marker='o' if row.frame_index == table.frame_index.iloc[0] else '^')
        axes[0, column].set_title(region+'\nLossless: PSNR=∞, SSIM=1')
        for axis, metric in zip(axes[:, column], ['PSNR (dB)', 'SSIM']):
            axis.set_xlabel('raw bytes / encoded bytes'); axis.set_ylabel(metric); axis.grid(True, alpha=.25)
    axes[1, -1].legend(fontsize=6)
    fig.suptitle('Compression quality — circles: primary frame; triangles: secondary frame')
    fig.tight_layout(rect=(0, 0, 1, .95)); save_fig(fig, 'm4_quality_vs_ratio', cfg); plt.close(fig)
    return table


def temporal_study(study):
    """Independent full-video baseline and JPEG passes, retaining compact evidence."""
    out, cfg, opts, m3 = study['out'], study['cfg'], study['options'], study['m3']
    curves, parameters, comparisons, frame_rows = {}, [], [], []
    for quality in [None]+opts['temporal_qualities']:
        label = 'baseline' if quality is None else f'jpeg_q{quality}'
        print(f'Temporal compression study: {label}', flush=True)
        encoded_current = None
        def transform(rgb):
            nonlocal encoded_current
            encoded_current, decoded = jpeg_roundtrip(rgb, quality)
            return decoded
        def observer(index, timestamp, original, decoded):
            row = dict(variant=label, frame_index=index, timestamp_s=timestamp,
                       raw_bytes=original.nbytes, encoded_bytes=len(encoded_current),
                       compression_ratio=original.nbytes/len(encoded_current), **_quality(original, decoded))
            if opts['save_all_frames']:
                folder = out/'temporal_jpeg'/label; folder.mkdir(parents=True, exist_ok=True)
                target = folder/f'{index:06d}.jpg'; target.write_bytes(encoded_current)
                row['path'] = str(target.relative_to(out))
            frame_rows.append(row)
        raw, _ = track_video(study['video'], study['roi'], **study['inits'][0], options=m3, scale=study['scale'],
                             frame_transform=transform if quality is not None else None,
                             frame_observer=observer if quality is not None else None)
        curve = clean_curve(raw, m3['max_gap_s'], m3['smooth_window_s'])
        if study['scale'] is not None:
            factor = 10/study['scale']
            for name in ('diameter_clean', 'diameter_smooth'): curve[name+'_mm'] = curve[name+'_px']*factor
            curve['area_smooth_mm2'] = curve.area_smooth_px2*factor**2
        curve.to_csv(out/f'{label}_pupil_curve.csv', index=False); curves[label] = curve
        params = response_parameters(curve, study['stimulus'], study['kind'], m3, study['scale'])
        parameters.append(dict(variant=label, **params))
        if quality is not None:
            comparisons.append(dict(variant=label, **compare_diameters(curves['baseline'], curve, study['scale'])))
            pd.DataFrame(frame_rows).to_csv(out/'temporal_compression_metrics.csv', index=False)
        # Persist completed passes even if a later pass fails or is cancelled.
        pd.DataFrame(parameters).to_csv(out/'physiological_parameters.csv', index=False)
        print(f'{label}: {len(curve)} frames; {curve.accepted.sum()} accepted', flush=True)
    summary = pd.DataFrame(comparisons); summary.to_csv(out/'diameter_comparison.csv', index=False)
    params = pd.DataFrame(parameters)
    numeric = [c for c in params if pd.api.types.is_numeric_dtype(params[c]) and c not in ('stimulus_s', 'accepted_fraction')]
    deltas = params[['variant', 'status']].copy()
    for name in numeric: deltas[name+'_delta'] = params[name]-params.iloc[0][name]
    deltas.to_csv(out/'physiological_differences.csv', index=False)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for label, curve in curves.items():
        axes[0].plot(curve.timestamp_s, curve.diameter_smooth_px, label=label)
        paired = curve.merge(curves['baseline'][['frame_index', 'accepted', 'equivalent_diameter_px']],
                             on='frame_index', suffixes=('', '_baseline'))
        use = paired.accepted & paired.accepted_baseline
        axes[1].plot(paired.loc[use, 'timestamp_s'], paired.loc[use, 'equivalent_diameter_px']-paired.loc[use, 'equivalent_diameter_px_baseline'], '.', label=label, markersize=3)
    axes[0].set_ylabel('Smoothed diameter (px)'); axes[0].legend()
    axes[1].set_ylabel('Paired raw difference (px)'); axes[1].set_xlabel('Time (s)')
    fig.tight_layout(); save_fig(fig, 'm4_temporal_diameter', cfg); plt.close(fig)
    manifest = json.loads((out/'manifest.json').read_text()); manifest['status'] = 'complete'
    manifest['temporal_frame_counts'] = {label: len(curve) for label, curve in curves.items()}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    return summary, params
