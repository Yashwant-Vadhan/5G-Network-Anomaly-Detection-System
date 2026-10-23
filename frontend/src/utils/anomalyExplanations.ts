/**
 * Human-friendly presentation templates and contextual guidance for network anomalies.
 *
 * Implements dual-audience presentation:
 * - Simple plain-English titles, explanations, and actions for everyday users
 * - Preserves technical accuracy without inventing physical causes or unverified handovers
 */

import { isValidMeasurement } from './measurement';

export interface AnomalyPresentationInfo {
  humanTitle: string;
  whatHappened: string;
  probableCauses: string;
  userAction: string;
  technicalAction: string;
  isRecovered: boolean;
}

export interface PresentationContext {
  anomalyType: string;
  isAnom?: boolean;
  severity?: string;
  eventStatus?: string;
  isRecovered?: boolean;
  rsrp?: number | null;
  deltaRsrp?: number | null;
  durationSec?: number | null;
  sampleCount?: number | null;
  previousPci?: number | string | null;
  currentPci?: number | string | null;
  previousNetwork?: string | null;
  currentNetwork?: string | null;
  backendDiagnosis?: string | null;
  backendRecommendation?: string | null;
}

export function getAnomalyPresentation(ctx: PresentationContext): AnomalyPresentationInfo {
  const type = String(ctx.anomalyType || 'NORMAL').toUpperCase();
  const isRecovered = Boolean(ctx.isRecovered);

  // 1. Recovered condition override for recommendations
  const recoveredAction = 'No action is needed. The measured signal has returned to an acceptable range.';

  switch (type) {
    case 'COMBINED_ANOMALY': {
      let whatHappened =
        'The reported cell identity changed while the signal met the configured poor-quality conditions. ' +
        'This may be associated with a temporary connectivity interruption during the transition.';
      if (ctx.previousPci !== undefined && ctx.previousPci !== null && ctx.currentPci !== undefined && ctx.currentPci !== null) {
        whatHappened = `Your phone switched from cell ${ctx.previousPci} to cell ${ctx.currentPci} while signal conditions were poor. A temporary connectivity interruption may have occurred.`;
      }
      return {
        humanTitle: 'Your phone changed cells while the signal was very weak.',
        whatHappened,
        probableCauses:
          'Coverage boundaries, physical obstacles, or cell reselection under weak radio conditions. ' +
          'The available measurements cannot establish a failed handover without network-side confirmation.',
        userAction: isRecovered
          ? recoveredAction
          : '• Wait 10–15 seconds for the connection to stabilize with the new cell tower.\n' +
            '• If poor signal persists, try moving toward an open area or window.\n' +
            '• Avoid active high-bandwidth streaming until cell synchronization completes.\n' +
            '• If the problem repeatedly occurs in this exact spot, consider reporting a coverage dead zone to your carrier.',
        technicalAction:
          '• Inspect PCI transition logs alongside temporal SS-RSRP and SS-SINR attenuation curves.\n' +
          '• Check whether handover execution occurred below A3 event measurement thresholds.\n' +
          '• Evaluate target cell beam signal quality to determine if ping-pong reselection is likely.',
        isRecovered,
      };
    }

    case 'SUDDEN_SIGNAL_DEGRADATION': {
      let whatHappened = 'Signal strength or quality deteriorated sharply over a short period.';
      if (isValidMeasurement(ctx.deltaRsrp)) {
        const dropMagnitude = Math.abs(Number(ctx.deltaRsrp)).toFixed(1);
        if (ctx.durationSec && ctx.durationSec > 0) {
          whatHappened = `Signal strength dropped by ${dropMagnitude} dB over ${Math.round(ctx.durationSec)} seconds.`;
        } else {
          whatHappened = `Signal strength dropped sharply by ${dropMagnitude} dB.`;
        }
      }
      return {
        humanTitle: 'Your 5G signal dropped suddenly.',
        whatHappened,
        probableCauses:
          'Changing coverage, a physical obstruction (such as an elevator, tinted window, or wall), or localized interference. ' +
          'The available measurements cannot establish the exact physical obstacle.',
        userAction: isRecovered
          ? recoveredAction
          : '• Check your immediate surroundings: moving away from concrete walls or metallic partitions helps restore signal.\n' +
            '• Ensure your mobile handset is not enclosed in an RF-shielding or conductive case.\n' +
            '• Monitor the live Signal Trends chart to confirm when signal levels climb back above -100 dBm.\n' +
            '• If you entered an elevator or underground space, connection will automatically recover upon exiting.',
        technicalAction:
          '• Analyze the rapid delta slope of SS-RSRP and SS-RSRQ to evaluate whether shadow fading or radio blockage occurred.\n' +
          '• Correlate signal drop timestamps with serving cell beam index changes.\n' +
          '• Verify if uplink transmission power reached maximum UE power class limits.',
        isRecovered,
      };
    }

    case 'PERSISTENT_POOR_QUALITY': {
      let whatHappened =
        'Signal strength or quality has remained below the configured limit across consecutive observations.';
      if (ctx.sampleCount && ctx.sampleCount > 1) {
        whatHappened = `The weak signal has persisted across ${ctx.sampleCount} consecutive readings.`;
      } else if (ctx.durationSec && ctx.durationSec > 0) {
        whatHappened = `Poor signal quality continued for ${Math.round(ctx.durationSec)} seconds.`;
      }
      return {
        humanTitle: 'Your network signal has remained weak.',
        whatHappened,
        probableCauses:
          'Operating at the fringe of base station coverage, dense building penetration loss, or continuous environmental attenuation.',
        userAction: isRecovered
          ? recoveredAction
          : '• Relocate closer to an exterior window or higher building elevation for direct radio path.\n' +
            '• Enable Wi-Fi Calling to ensure voice and messaging continuity in weak indoor coverage.\n' +
            '• If moving outdoors does not improve reception, verify whether your mobile carrier reports maintenance.\n' +
            '• Avoid initiating large file downloads or video conferences until signal quality recovers.',
        technicalAction:
          '• Verify serving cell sector coverage boundaries and evaluate link budget margin.\n' +
          '• Cross-check SS-RSRQ to distinguish base station range deficit from heavy channel interference.\n' +
          '• Audit CSI-RS report history to inspect beamforming gain consistency.',
        isRecovered,
      };
    }

    case 'SIGNAL_DEGRADATION': {
      let whatHappened = 'One or more measured signal values crossed the configured poor-quality threshold.';
      if (isValidMeasurement(ctx.rsrp)) {
        whatHappened = `Measured signal strength is ${Number(ctx.rsrp).toFixed(1)} dBm, which is below the nominal threshold.`;
      }
      return {
        humanTitle: 'Your current signal quality is poor.',
        whatHappened,
        probableCauses:
          'Distance from the base station, localized path loss, or environmental obstruction. Evidence does not establish severe interference.',
        userAction: isRecovered
          ? recoveredAction
          : '• Check whether the signal improves after a brief wait or a small change in your physical location.\n' +
            '• If you are stationary, a brief 5-10 second pause allows carrier beam steering to optimize reception.\n' +
            '• Check the Signal Trends tab to monitor whether the rolling average trend is stabilizing.\n' +
            '• If signal recovers to nominal levels, no further action or settings adjustment is needed.',
        technicalAction:
          '• Monitor signal recovery trajectory and evaluate SS-SINR noise levels.\n' +
          '• Track temporal RSSI baseline to assess channel fading characteristics.\n' +
          '• Verify that UE receiver sensitivity conforms to 3GPP Band n78 minimum requirements.',
        isRecovered,
      };
    }

    case 'CELL_TRANSITION': {
      let whatHappened =
        'A change in the reported physical cell identity was observed. Cell transitions can be a normal part of mobile connectivity.';
      if (ctx.previousPci !== undefined && ctx.previousPci !== null && ctx.currentPci !== undefined && ctx.currentPci !== null) {
        whatHappened = `Your phone switched from cell ${ctx.previousPci} to cell ${ctx.currentPci}.`;
      }
      return {
        humanTitle: 'Your phone switched to another network cell.',
        whatHappened,
        probableCauses:
          'Normal mobile device movement or carrier load balancing between adjacent radio towers.',
        userAction: isRecovered
          ? recoveredAction
          : '• No action is required: cell changes are normal behavior (Guardrail G6) as your phone moves.\n' +
            '• The cellular network automatically transfers your data connection to the target cell.\n' +
            '• If your connection has stabilized, standard high-speed 5G performance will resume immediately.\n' +
            '• If signal repeatedly drops during cell transitions, review the Cells & Network page for handover frequency.',
        technicalAction:
          '• Review handover sequence parameters and neighbor cell signal thresholds.\n' +
          '• Inspect target cell PCI and NRARFCN carrier frequency alignment.\n' +
          '• Verify that handover execution delay did not exceed 3GPP RRC reconfiguration targets.',
        isRecovered,
      };
    }

    case 'NETWORK_STATE_TRANSITION': {
      const prevNet = String(ctx.previousNetwork || '').toUpperCase();
      const currNet = String(ctx.currentNetwork || '').toUpperCase();
      const is5gTo4g = prevNet.includes('5G') && (currNet.includes('4G') || currNet.includes('LTE'));

      const whatHappened = is5gTo4g
        ? 'Your phone switched from 5G to 4G. This can happen when 5G coverage becomes unsuitable, while 4G may continue providing connectivity.'
        : prevNet && currNet && prevNet !== currNet
        ? `Your device-reported network connection changed from ${prevNet} to ${currNet}.`
        : 'Your phone changed its network operating state.';

      return {
        humanTitle: "Your phone's network connection changed.",
        whatHappened,
        probableCauses:
          '5G coverage boundary, secondary carrier de-allocation, or mobile core state reconfiguration.',
        userAction: isRecovered
          ? recoveredAction
          : '• Your connection remains active on 4G LTE; basic browsing, calling, and messaging continue seamlessly.\n' +
            '• High-speed 5G will automatically reconnect once you return to an area with robust 5G coverage.\n' +
            '• If you want to force immediate 5G re-scan, toggle Airplane Mode on and off once.\n' +
            '• If 4G performance is sufficient for your current tasks, no manual action is necessary.',
        technicalAction:
          '• Verify LTE anchor stability and 5G secondary cell release triggers.\n' +
          '• Check whether B1/B2 measurement reports triggered secondary node release.\n' +
          '• Inspect EN-DC Dual Connectivity split bearer release metrics.',
        isRecovered,
      };
    }

    case 'STATISTICAL_ONLY': {
      return {
        humanTitle: 'An unusual network pattern was detected.',
        whatHappened:
          'The anomaly detector identified an unusual combination of measurements, but the available evidence does not identify a specific physical event.',
        probableCauses:
          'Statistical variance across multiple telemetry features without breaching rule-based limits.',
        userAction: isRecovered
          ? recoveredAction
          : '• Continue normal device usage: your phone is connected and active data sessions are unaffected.\n' +
            '• The AI isolation model is tracking multi-dimensional features to observe whether values normalize.\n' +
            '• No reset, airplane mode toggle, or phone restart is required at this time.\n' +
            '• If you experience noticeable browsing sluggishness, check the Signal Trends tab for noise spikes.',
        technicalAction:
          'Examine multi-variate feature contributions to the anomaly score.\n' +
          '• Correlate baseline Z-score feature vectors with rolling average trends.\n' +
          '• Verify whether temporal feature drift or rapid Doppler shifts caused statistical divergence.',
        isRecovered,
      };
    }

    case 'COVERAGE_HOLE': {
      return {
        humanTitle: 'Your phone entered a weak coverage area.',
        whatHappened:
          ctx.backendDiagnosis ||
          'Signal strength dropped significantly below operational levels in the serving area.',
        probableCauses:
          'Sparse cell tower spacing, physical blockage, or indoor structural attenuation.',
        userAction: isRecovered
          ? recoveredAction
          : (ctx.backendRecommendation
            ? `${ctx.backendRecommendation}\n• Try moving closer to an exterior window or higher floor to regain direct line-of-sight.\n• If indoors, avoid subterranean basements or thick interior concrete structures.\n• Enable Wi-Fi Calling to maintain uninterrupted voice call and SMS connectivity.`
            : '• Try moving closer to an exterior window or higher floor to regain direct line-of-sight.\n• If indoors, avoid subterranean basements or thick interior concrete structures.\n• Enable Wi-Fi Calling to maintain uninterrupted voice call and SMS connectivity.\n• If coverage hole is persistent at home/office, consider requesting an indoor femtocell or carrier booster.'),
        technicalAction:
          '• Assess downlink RSRP against coverage planning limits.\n' +
          '• Check whether neighboring base station sectors can provide overlapping coverage.\n' +
          '• Evaluate whether transmission power boost or antenna downtilt adjustment is needed on nearby gNodeB.',
        isRecovered,
      };
    }

    case 'INTERFERENCE': {
      return {
        humanTitle: 'Radio signal interference detected.',
        whatHappened:
          ctx.backendDiagnosis ||
          'Signal quality and signal-to-interference ratio degraded while signal strength remained present.',
        probableCauses:
          'Co-channel interference from overlapping neighbor sectors or localized radio noise.',
        userAction: isRecovered
          ? recoveredAction
          : (ctx.backendRecommendation
            ? `${ctx.backendRecommendation}\n• Allow 10–15 seconds for base station beamforming or carrier re-selection algorithms to adapt.\n• If speed remains heavily throttled, toggle Airplane Mode once to re-attach to an interference-free carrier.\n• Moving slightly away from large electronic appliances or industrial machinery can reduce local noise.`
            : '• Allow 10–15 seconds for base station beamforming or carrier re-selection algorithms to adapt.\n• If speed remains heavily throttled, toggle Airplane Mode once to re-attach to an interference-free carrier.\n• Moving slightly away from large electronic appliances or industrial machinery can reduce local noise.\n• Monitor the SS-SINR chart on the Signal Trends page to observe when channel clarity improves.'),
        technicalAction:
          '• Inspect SS-SINR degradation and neighbor cell power levels.\n' +
          '• Check PRB (Physical Resource Block) utilization and inter-cell interference coordination (ICIC) logs.\n' +
          '• Evaluate whether neighbor cell PCI modulo 3 collision is affecting reference signal reception.',
        isRecovered,
      };
    }

    case 'NORMAL':
    default: {
      return {
        humanTitle: 'Normal network operating conditions.',
        whatHappened: 'Normal network operating conditions. No active anomaly event.',
        probableCauses: 'Cellular radio link is operating nominally across all measured frequency carriers.',
        userAction:
          '• The local LLM and multi-agent diagnostic engine confirms nominal 5G network performance.\n' +
          '• All RF telemetry parameters (SS-RSRP, SS-RSRQ, SS-SINR) remain well within 3GPP operational limits.\n' +
          '• High-speed data streaming, ultra-low latency applications, and clear voice calls are fully supported.\n' +
          '• Passive continuous monitoring remains active in the background — no user action is required.',
        technicalAction:
          '• Continue standard passive telemetry collection.\n' +
          '• Model feature distributions remain aligned with the baseline nominal profile.\n' +
          '• Isolation Forest decision function score indicates stable in-distribution operation.',
        isRecovered: false,
      };
    }
  }
}
