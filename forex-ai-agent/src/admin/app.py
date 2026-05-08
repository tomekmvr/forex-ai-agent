from __future__ import annotations

import pandas as pd
import streamlit as st

from src.admin.services import close_admin_position, get_symbol_presets, run_admin_snapshot, submit_admin_order
from src.admin.ui_defaults import build_runtime_hint, resolve_default_execution_mode, resolve_default_source_mode


def main() -> None:
    st.set_page_config(page_title="Forex AI Agent Admin", page_icon="FX", layout="wide")
    st.title("Forex AI Agent Admin Panel")
    st.caption("Lokalny panel nad orchestratoriem, agentami analitycznymi i bramkami ryzyka.")

    default_source_mode = resolve_default_source_mode()
    default_execution_mode = resolve_default_execution_mode()
    source_mode_options = ["auto", "demo", "broker"]
    execution_mode_options = ["paper", "live"]

    with st.sidebar:
        st.header("Sterowanie")
        source_mode = st.selectbox(
            "Źródło danych",
            options=source_mode_options,
            index=source_mode_options.index(default_source_mode),
        )
        execution_mode = st.selectbox(
            "Execution mode",
            options=execution_mode_options,
            index=execution_mode_options.index(default_execution_mode),
        )
        preset_symbols = get_symbol_presets(source_mode)
        preset_symbol = st.selectbox("Preset symbol", options=preset_symbols, index=0)
        instrument = st.text_input("Instrument", value=preset_symbol)
        granularity = st.selectbox("Granularity", options=["M15", "H1", "H4", "D"], index=1)
        periods = st.slider("Liczba świec", min_value=40, max_value=400, value=120, step=10)
        equity = st.number_input("Equity", min_value=1_000.0, value=100_000.0, step=1_000.0)
        session_start_equity = st.number_input(
            "Equity na starcie dnia",
            min_value=1_000.0,
            value=100_000.0,
            step=1_000.0,
        )
        current_equity = st.number_input("Bieżące equity", min_value=0.0, value=99_200.0, step=1_000.0)
        win_probability = st.slider("Win probability", min_value=0.05, max_value=0.95, value=0.57, step=0.01)
        payoff_ratio = st.slider("Payoff ratio", min_value=0.5, max_value=5.0, value=1.8, step=0.1)
        failure_probability = st.slider(
            "Failure probability",
            min_value=0.0,
            max_value=0.95,
            value=0.08,
            step=0.01,
        )

    runtime_hint = build_runtime_hint(source_mode)
    if runtime_hint:
        st.warning(runtime_hint)

    snapshot = run_admin_snapshot(
        equity=equity,
        session_start_equity=session_start_equity,
        current_equity=current_equity,
        instrument=instrument,
        granularity=granularity,
        periods=periods,
        source_mode=source_mode,
        win_probability=win_probability,
        payoff_ratio=payoff_ratio,
        failure_probability=failure_probability,
    )

    decision = snapshot.orchestrator_decision
    risk = snapshot.risk_decision

    metric_columns = st.columns(5)
    metric_columns[0].metric("Signal", decision.final_signal)
    metric_columns[1].metric("Confidence", f"{decision.confidence:.2%}")
    metric_columns[2].metric("Weighted Score", f"{decision.weighted_score:.4f}")
    metric_columns[3].metric("Approved", "YES" if risk.approved else "NO")
    metric_columns[4].metric("Kill Switch", "ON" if snapshot.kill_switch_state.triggered else "OFF")

    st.info(f"Data source: {snapshot.source_name}. {snapshot.status_message}")

    left_column, right_column = st.columns([1.5, 1.0])

    with left_column:
        st.subheader("Cena i zmienność")
        st.line_chart(snapshot.market_features[["close", "realized_volatility"]])
        st.subheader("Agent Breakdown")
        agent_rows = [
            {
                "agent": signal.agent_name,
                "signal": signal.signal,
                "confidence": signal.confidence,
                "reasoning": signal.reasoning,
            }
            for signal in decision.agent_signals
        ]
        st.dataframe(pd.DataFrame(agent_rows), use_container_width=True)

    with right_column:
        st.subheader("Account State")
        st.json(snapshot.account_snapshot.to_record())
        st.subheader("Risk Gate")
        st.write(risk.reasoning)
        st.json(
            {
                "capital_fraction": risk.capital_fraction,
                "risk_budget": risk.risk_budget,
                "position_units": risk.position_units,
                "expected_transaction_cost": risk.expected_transaction_cost,
                "kill_switch_triggered": risk.kill_switch_triggered,
                "diagnostics": dict(risk.diagnostics),
            }
        )
        st.subheader("Kill Switch State")
        st.json(
            {
                "triggered": snapshot.kill_switch_state.triggered,
                "drawdown": snapshot.kill_switch_state.drawdown,
                "remaining_buffer": snapshot.kill_switch_state.remaining_drawdown_buffer,
                "reason": snapshot.kill_switch_state.reason,
            }
        )
        st.subheader("Orchestrator Reasoning")
        st.write(decision.reasoning)

    st.subheader("Open Positions")
    if snapshot.positions.empty:
        st.caption("No open positions available from the selected source.")
    else:
        st.dataframe(snapshot.positions, use_container_width=True)

    if snapshot.source_name == "tms_oanda_mt5" or (source_mode == "broker" and instrument.endswith(".pro")):
        st.subheader("MT5 Order Entry")
        with st.form("mt5_order_form"):
            order_side = st.selectbox("Side", options=["buy", "sell"], index=0)
            order_volume = st.number_input("Volume", min_value=0.01, value=0.10, step=0.01, format="%.2f")
            order_comment = st.text_input("Comment", value="Forex AI Agent Admin")
            live_order_confirmed = st.checkbox("Potwierdzam wysłanie zlecenia live", value=False)
            submit_order = st.form_submit_button("Wyślij zlecenie MT5")

        if submit_order:
            try:
                execution_result = submit_admin_order(
                    source_mode=source_mode,
                    instrument=instrument,
                    side=order_side,
                    volume=order_volume,
                    execution_mode=execution_mode,
                    confirm_live_execution=live_order_confirmed,
                    comment=order_comment,
                )
                if execution_result.success:
                    st.success(execution_result.message)
                else:
                    st.error(execution_result.message)
                st.json(execution_result.to_record())
            except Exception as exc:
                st.error(f"MT5 order submission failed: {exc}")

        if not snapshot.positions.empty and "position_id" in snapshot.positions.columns:
            st.subheader("MT5 Close Position")
            position_options = {
                f"{row.instrument} | {row.side} | {row.units} | {row.position_id}": row
                for row in snapshot.positions.itertuples(index=False)
            }
            with st.form("mt5_close_form"):
                selected_position_label = st.selectbox("Position", options=list(position_options.keys()))
                close_comment = st.text_input("Close comment", value="Forex AI Agent Admin close")
                live_close_confirmed = st.checkbox("Potwierdzam zamknięcie pozycji live", value=False)
                close_position_clicked = st.form_submit_button("Zamknij pozycję MT5")

            if close_position_clicked:
                try:
                    selected_position = position_options[selected_position_label]
                    close_result = close_admin_position(
                        source_mode=source_mode,
                        instrument=selected_position.instrument,
                        position_id=str(selected_position.position_id),
                        volume=float(selected_position.units),
                        side=str(selected_position.side),
                        execution_mode=execution_mode,
                        confirm_live_execution=live_close_confirmed,
                        comment=close_comment,
                    )
                    if close_result.success:
                        st.success(close_result.message)
                    else:
                        st.error(close_result.message)
                    st.json(close_result.to_record())
                except Exception as exc:
                    st.error(f"MT5 close position failed: {exc}")

    st.subheader("Trade History")
    if snapshot.trade_history.empty:
        st.caption("No trade history available from the selected source.")
    else:
        st.dataframe(snapshot.trade_history, use_container_width=True)

    st.subheader("News and Calendar Inputs")
    bottom_left, bottom_right = st.columns(2)
    with bottom_left:
        st.dataframe(snapshot.news_features, use_container_width=True)
    with bottom_right:
        st.dataframe(snapshot.calendar_features, use_container_width=True)


if __name__ == "__main__":
    main()
