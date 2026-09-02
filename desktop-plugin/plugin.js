import { jsx } from 'react/jsx-runtime';
import { StatusDot } from '@hermes/plugin-sdk';

export default {
    id: 'light-on-llm',
    name: 'Light-on-LLM Desktop Indicator',
    register(ctx) {
        console.log('[Light-on-LLM] Polling desktop plugin registered.');

        async function setLight(state, isCloud = true) {
            try {
                await ctx.rest('/set-light', {
                    method: 'POST',
                    body: { state, isCloud }
                });
            } catch (_err) {
                // Ignore transient errors during polling.
            }
        }

        let lastState = 'IDLE';

        setInterval(async () => {
            try {
                const sessions = await ctx.host.request('sessions.list', {});
                const list = Array.isArray(sessions) ? sessions : (sessions?.sessions || []);
                const active = list.find(s => s.status === 'running' || s.running === true || s.active === true);
                const newState = active ? 'THINKING' : 'IDLE';

                if (newState !== lastState) {
                    lastState = newState;
                    const model = ctx.host.state.model.get() || '';
                    const isCloud = !model.endsWith('.gguf');
                    console.log('[Light-on-LLM] State changed:', newState, { model, isCloud });
                    setLight(newState, isCloud);
                }
            } catch (_err) {
                // Silent catch for poll errors.
            }
        }, 1000);

        ctx.register({
            id: 'light-status',
            area: 'statusBar.right',
            render: () => {
                return jsx('div', {
                    style: { display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', padding: '0 6px' },
                    title: 'Click to set the light to idle green',
                    onClick: () => setLight('IDLE', true),
                    children: [
                        jsx(StatusDot, { status: 'online' }),
                        'Light'
                    ]
                });
            }
        });
    }
};
